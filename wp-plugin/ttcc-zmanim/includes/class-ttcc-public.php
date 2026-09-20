<?php
/**
 * Public surfaces: current-week widget shortcode, browse shortcode, and the
 * piSignage full-page endpoint. All read-only. Rendered HTML is cached
 * (transient) with a persistent "last-good" fallback so a service outage does
 * not blank the public pages.
 *
 * @package TTCC_Zmanim
 */

defined( 'ABSPATH' ) || exit;

class TTCC_Zmanim_Public {

	const CACHE_TTL   = 3 * HOUR_IN_SECONDS;
	const LASTGOOD_KEY = 'ttcc_lastgood_';

	public function hooks() {
		add_action( 'init', array( __CLASS__, 'add_rewrite_rules' ) );
		add_filter( 'query_vars', array( $this, 'query_vars' ) );
		add_action( 'template_redirect', array( $this, 'maybe_render_signage' ) );
		add_shortcode( 'ttcc_week', array( $this, 'shortcode_week' ) );
		add_shortcode( 'ttcc_browse', array( $this, 'shortcode_browse' ) );
		add_shortcode( 'ttcc_shabbos', array( 'TTCC_Zmanim_Shabbos', 'shortcode_widget' ) );
		add_action( 'wp_enqueue_scripts', array( $this, 'enqueue' ) );
	}

	public function enqueue() {
		wp_register_style( 'ttcc-public', TTCC_ZMANIM_URL . 'public/css/public.css', array(), TTCC_ZMANIM_VERSION );
		wp_enqueue_style( 'ttcc-public' );
	}

	public static function add_rewrite_rules() {
		// The preview must register before BOTH slug rules: 'preview' would
		// otherwise be captured as a slug by the generic rule and 404 against
		// the real one. (A slug is a 20-character generated token, so this
		// cannot take a live screen's URL away from it.)
		add_rewrite_rule( '^ttcc-signage/preview/?$', 'index.php?ttcc_signage=1&ttcc_view=preview', 'top' );
		// The /shabbos variant must register before the generic slug rule.
		add_rewrite_rule( '^ttcc-signage/([^/]+)/shabbos/?$', 'index.php?ttcc_signage=1&ttcc_slug=$matches[1]&ttcc_view=shabbos', 'top' );
		add_rewrite_rule( '^ttcc-signage/([^/]+)/?$', 'index.php?ttcc_signage=1&ttcc_slug=$matches[1]', 'top' );
	}

	public function query_vars( $vars ) {
		$vars[] = 'ttcc_signage';
		$vars[] = 'ttcc_slug';
		$vars[] = 'ttcc_view';
		return $vars;
	}

	// --- current-week helpers ----------------------------------------------

	/** ISO date of the current week's Sunday, in the site timezone. */
	public static function current_sunday() {
		$now = current_datetime(); // WP 5.3+, site tz.
		$dow = (int) $now->format( 'w' ); // 0 = Sunday.
		$sun = $now->modify( '-' . $dow . ' days' );
		return $sun->format( 'Y-m-d' );
	}

	public static function week_end( $sunday_iso ) {
		$d = date_create( $sunday_iso );
		if ( ! $d ) {
			return $sunday_iso;
		}
		$d->modify( '+6 days' );
		return $d->format( 'Y-m-d' );
	}

	/**
	 * Rendered full HTML for a range, cached with last-good fallback.
	 * $context distinguishes cache buckets (e.g. 'week', 'signage').
	 *
	 * When a saved timesheet overlaps the range, its dashboard edits (line
	 * overrides + note edits) are applied, so the public pages and signage
	 * match the edited sheet. The sheet's id + updated_at are part of the
	 * cache key: re-saving a sheet in the dashboard takes effect on the next
	 * page load instead of waiting out the cache TTL.
	 *
	 * Returns HTML string, or '' if nothing (not even last-good) is available.
	 *
	 * $persist false is the preview's mode: the rendered week is still cached
	 * (stepping through a Yom Tov should not re-render the same week each time)
	 * but it never becomes the persistent last-good copy, and a failure is not
	 * papered over with one. A preview of some other week must not be what a
	 * screen falls back to during an outage, and a preview that quietly showed
	 * last-good under a date box saying otherwise would be worse than one that
	 * says it could not render.
	 */
	public static function cached_html( $start, $end, $context = 'week', $inject_css = '', $persist = true ) {
		$sheet     = TTCC_Zmanim_Storage::find_overlapping( $start, $end );
		$overrides = ( $sheet && is_array( $sheet['overrides'] ) ) ? $sheet['overrides'] : array();
		$stamp     = $sheet ? $sheet['id'] . '|' . $sheet['updated_at'] : 'none';

		$stable = self::LASTGOOD_KEY . md5( $context . '|' . $start . '|' . $end . '|' . $inject_css );
		$key    = $stable . '_' . md5( $stamp );
		$cached = get_transient( $key );
		if ( false !== $cached ) {
			return $cached;
		}

		$built = TTCC_Zmanim_Sheet::build( $start, $end, $overrides );
		if ( is_wp_error( $built ) ) {
			if ( ! $persist ) {
				return '';
			}
			$lastgood = get_option( $stable, '' );
			return $lastgood ? $lastgood : '';
		}
		$res = TTCC_Zmanim_Service_Client::render_html_doc( $built['doc'] );
		if ( is_wp_error( $res ) ) {
			if ( ! $persist ) {
				return '';
			}
			$lastgood = get_option( $stable, '' );
			return $lastgood ? $lastgood : '';
		}
		$html = $res['html'];
		if ( $inject_css ) {
			$html = self::inject_head( $html, $inject_css );
		}
		set_transient( $key, $html, self::CACHE_TTL );
		if ( $persist ) {
			update_option( $stable, $html, false ); // persistent last-good (stable key).
		}
		return $html;
	}

	/**
	 * Drop every cached sheet render and its last-good copy.
	 *
	 * Same reasoning as TTCC_Zmanim_Shabbos::flush(): these are keyed by date
	 * range and never by engine version, so a service deploy leaves the public
	 * pages and the piSignage sheet serving the times from before it.
	 */
	public static function flush() {
		global $wpdb;
		// Both live under LASTGOOD_KEY: the render is cached as the transient
		// "<LASTGOOD_KEY><md5>_<md5>" and the last-good copy is the option
		// "<LASTGOOD_KEY><md5>" (see cached_html), so one prefix finds both —
		// the transients through their _transient_ row, the options directly.
		$prefix = self::LASTGOOD_KEY;
		foreach ( array( '_transient_' . $prefix, $prefix ) as $like_prefix ) {
			$like = $wpdb->esc_like( $like_prefix ) . '%';
			// phpcs:ignore WordPress.DB.DirectDatabaseQuery -- prefix sweep, no API for it.
			$names = $wpdb->get_col( $wpdb->prepare( "SELECT option_name FROM $wpdb->options WHERE option_name LIKE %s", $like ) );
			foreach ( (array) $names as $name ) {
				if ( 0 === strpos( $name, '_transient_timeout_' ) ) {
					continue;  // swept with its value by delete_transient
				}
				if ( 0 === strpos( $name, '_transient_' ) ) {
					delete_transient( substr( $name, strlen( '_transient_' ) ) );
				} else {
					delete_option( $name );
				}
			}
		}
	}

	private static function inject_head( $html, $snippet ) {
		$pos = stripos( $html, '</head>' );
		if ( false === $pos ) {
			return $snippet . $html;
		}
		return substr( $html, 0, $pos ) . $snippet . substr( $html, $pos );
	}

	/** Wrap a self-contained sheet-HTML document in an auto-sizing iframe (srcdoc). */
	private static function iframe( $html, $title ) {
		if ( '' === $html ) {
			return '<div class="ttcc-embed-empty">' . esc_html__( 'Times are temporarily unavailable.', 'ttcc-zmanim' ) . '</div>';
		}
		$srcdoc = esc_attr( $html );
		return sprintf(
			'<iframe class="ttcc-embed" title="%s" srcdoc="%s" style="width:100%%;border:0;min-height:600px;" onload="try{this.style.height=(this.contentWindow.document.body.scrollHeight+20)+\'px\'}catch(e){}"></iframe>',
			esc_attr( $title ),
			$srcdoc
		);
	}

	// --- shortcodes ---------------------------------------------------------

	/** [ttcc_week] — current week, auto-rolling. */
	public function shortcode_week( $atts ) {
		$sunday = self::current_sunday();
		$html   = self::cached_html( $sunday, self::week_end( $sunday ), 'week' );
		return self::iframe( $html, __( 'This week at TTCC', 'ttcc-zmanim' ) );
	}

	/**
	 * [ttcc_browse] — pick any week (Sunday). Read-only; editing stays in
	 * wp-admin (the browse-page inline-edit stretch goal is deferred).
	 */
	public function shortcode_browse( $atts ) {
		$req    = isset( $_GET['ttcc_wk'] ) ? sanitize_text_field( wp_unslash( $_GET['ttcc_wk'] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification.Recommended
		$sunday = preg_match( '/^\d{4}-\d{2}-\d{2}$/', $req ) ? $req : self::current_sunday();
		$html   = self::cached_html( $sunday, self::week_end( $sunday ), 'week' );

		$form = sprintf(
			'<form method="get" class="ttcc-browse-form"><label>%s <input type="date" name="ttcc_wk" value="%s"></label> <button type="submit">%s</button></form>',
			esc_html__( 'Week of (Sunday):', 'ttcc-zmanim' ),
			esc_attr( $sunday ),
			esc_html__( 'View', 'ttcc-zmanim' )
		);
		return '<div class="ttcc-browse">' . $form . self::iframe( $html, __( 'TTCC times', 'ttcc-zmanim' ) ) . '</div>';
	}

	// --- piSignage ----------------------------------------------------------

	// --- preview ------------------------------------------------------------

	/** Nonce action guarding the signage preview route. */
	const PREVIEW_NONCE = 'ttcc_signage_preview';

	/**
	 * URL of the signage preview for a given moment.
	 *
	 * Public so the display plugin's preview page can offer these screens
	 * alongside its own, the same way it reads this plugin's profile set for
	 * minyan times: one implementation of each screen, wherever it is viewed
	 * from. `$at` is a DateTimeInterface in the site timezone; `$view` is
	 * 'sheet' (the week's sheet, laid out to fill the panel) or 'shabbos'.
	 */
	public static function preview_url( $at, $view = 'sheet' ) {
		return add_query_arg(
			array(
				'at'       => $at->format( 'Y-m-d\TH:i' ),
				'view'     => ( 'shabbos' === $view ) ? 'shabbos' : 'sheet',
				'_wpnonce' => wp_create_nonce( self::PREVIEW_NONCE ),
			),
			home_url( '/ttcc-signage/preview/' )
		);
	}

	/**
	 * Parse an `at` parameter ("YYYY-MM-DDTHH:MM", site timezone). Returns null
	 * when missing or malformed, so the caller decides what that means rather
	 * than silently previewing now.
	 */
	public static function parse_at( $raw ) {
		$raw = is_string( $raw ) ? trim( $raw ) : '';
		if ( ! preg_match( '/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/', $raw ) ) {
			return null;
		}
		$at = DateTimeImmutable::createFromFormat( 'Y-m-d\TH:i', $raw, wp_timezone() );
		if ( ! $at ) {
			return null;
		}
		// createFromFormat takes the unspecified seconds from the current clock,
		// which would make two previews of the same moment differ.
		return $at->setTime( (int) $at->format( 'H' ), (int) $at->format( 'i' ), 0 );
	}

	/**
	 * Either signage screen, rendered for an arbitrary week.
	 *
	 * Admin-only, by capability and nonce. Not for secrecy — these times are on
	 * a wall and published on the site — but each preview is a server-side
	 * render of a week through the engine, and an open URL is a way to make the
	 * site render a year of them one request at a time. It also keeps the
	 * screens' own slug URLs the only public way in, so previewing a date can
	 * never hand one out.
	 *
	 * Deliberately the same renderers the screens use, with the week (and, for
	 * the Shabbos board, the clock) handed to them: a preview drawn by separate
	 * code could only ever show what that separate code does.
	 */
	private static function render_preview() {
		nocache_headers();
		header( 'X-Robots-Tag: noindex, nofollow', true );

		if ( ! current_user_can( TTCC_ZMANIM_CAP ) ) {
			status_header( 403 );
			wp_die(
				esc_html__( 'You do not have permission to preview the screens.', 'ttcc-zmanim' ),
				'',
				array( 'response' => 403 )
			);
		}
		// phpcs:ignore WordPress.Security.NonceVerification.Recommended -- verified on the next line.
		$nonce = isset( $_GET['_wpnonce'] ) ? sanitize_text_field( wp_unslash( $_GET['_wpnonce'] ) ) : '';
		if ( ! wp_verify_nonce( $nonce, self::PREVIEW_NONCE ) ) {
			status_header( 403 );
			wp_die(
				esc_html__( 'This preview link has expired. Reload the page you opened it from.', 'ttcc-zmanim' ),
				'',
				array( 'response' => 403 )
			);
		}

		// phpcs:ignore WordPress.Security.NonceVerification.Recommended -- nonce verified above.
		$at = self::parse_at( isset( $_GET['at'] ) ? wp_unslash( $_GET['at'] ) : '' );
		if ( null === $at ) {
			$at = current_datetime();
		}
		// phpcs:ignore WordPress.Security.NonceVerification.Recommended -- nonce verified above.
		$view   = ( isset( $_GET['view'] ) && 'shabbos' === $_GET['view'] ) ? 'shabbos' : 'sheet';
		$sunday = TTCC_Zmanim_Shabbos::sunday_of( $at->format( 'Y-m-d' ) );

		header( 'Content-Type: text/html; charset=utf-8' );

		if ( 'shabbos' === $view ) {
			TTCC_Zmanim_Shabbos::render_signage_screen( $sunday, $at );
			exit;
		}

		$html = self::cached_html( $sunday, self::week_end( $sunday ), 'signage', self::signage_head(), false );
		if ( '' === $html ) {
			echo '<!doctype html><meta charset="utf-8"><body style="font:2.5vw sans-serif;text-align:center;padding:20vh;color:#444">'
				. esc_html__( 'This week could not be rendered — the sheet service did not answer.', 'ttcc-zmanim' )
				. '</body>';
			exit;
		}
		// No meta-refresh, unlike the live screen: a preview that reloaded
		// itself every half hour would jump back to whatever week the reloaded
		// URL asks for while somebody is looking at it.
		echo $html; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- self-contained service HTML.
		exit;
	}

	public function maybe_render_signage() {
		if ( ! get_query_var( 'ttcc_signage' ) ) {
			return;
		}
		// The preview is gated by capability and nonce rather than by the slug,
		// so it is handled before the slug is looked at at all.
		if ( 'preview' === (string) get_query_var( 'ttcc_view' ) ) {
			self::render_preview();
			exit;
		}

		$slug = (string) get_query_var( 'ttcc_slug' );
		$want = TTCC_Zmanim_Settings::pisignage_slug();
		if ( ! $want || ! hash_equals( $want, $slug ) ) {
			status_header( 404 );
			nocache_headers();
			exit;
		}

		// /ttcc-signage/<slug>/shabbos/ — the Shabbos & Yom Tov screen
		// (portrait, large-type, self-refreshing; see TTCC_Zmanim_Shabbos).
		if ( 'shabbos' === (string) get_query_var( 'ttcc_view' ) ) {
			nocache_headers();
			header( 'Content-Type: text/html; charset=utf-8' );
			TTCC_Zmanim_Shabbos::render_signage_screen();
			exit;
		}

		$sunday = self::current_sunday();
		$html   = self::cached_html( $sunday, self::week_end( $sunday ), 'signage', self::signage_head() );

		nocache_headers();
		header( 'Content-Type: text/html; charset=utf-8' );
		if ( '' === $html ) {
			echo '<!doctype html><meta charset="utf-8"><body style="font:4vw sans-serif;text-align:center;padding:20vh">Times temporarily unavailable</body>';
			exit;
		}
		// Auto-advance to the next week when the clock rolls over: refresh hourly.
		$html = self::inject_head_static( $html, '<meta http-equiv="refresh" content="1800">' );
		echo $html; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- self-contained service HTML.
		exit;
	}

	private static function inject_head_static( $html, $snippet ) {
		$pos = stripos( $html, '</head>' );
		if ( false === $pos ) {
			return $snippet . $html;
		}
		return substr( $html, 0, $pos ) . $snippet . substr( $html, $pos );
	}

	/**
	 * Signage sizing: the panel IS the page.
	 *
	 * A screen has no scrollbar and nobody standing at it to pinch-zoom, so
	 * anything outside the display is simply lost. Rather than scale an A4 sheet
	 * to the screen and letterbox it — which wastes 60% of a landscape panel,
	 * since A4 is portrait — the .page box is made the viewport, and the sheet's
	 * own fit-to-page pass (engine/page_layout.py) lays the week out inside it
	 * exactly as it would on paper. One URL then suits a screen hung either way
	 * up, at the largest type the panel allows, with nothing off the edge. The
	 * raised --ttcc-fit-max lets that pass magnify past its print ceiling, which
	 * a 4K panel needs.
	 *
	 * (Fixed zoom factors used to do this job and could not: 2.1x made the page
	 * 2357px tall, more than a screen height off the bottom of a 1080p panel,
	 * and a zoomed body is also `zoom` x wider than the screen, which pushed the
	 * sheet off to the right.)
	 *
	 * The margin is in vmin so the border round the sheet stays even and scales
	 * with the panel; it doubles as insurance against a TV that overscans.
	 *
	 * A screen shows one page at a time, so a week that needs more than one —
	 * Sukkos, where the yom-tov days push the block count past four — cycles
	 * through them instead of quietly showing the first and dropping the rest.
	 */
	private static function signage_head() {
		return '<style id="ttcc-signage">'
			. ':root{--ttcc-fit-max:4}'
			. 'html,body{margin:0;padding:0;background:#fff;overflow:hidden}'
			. '.page{width:100vw!important;height:100vh!important;'
			. 'margin:0!important;box-shadow:none}'
			. '.page-margin{left:3vmin!important;right:3vmin!important;'
			. 'top:3vmin!important;bottom:3vmin!important}'
			. '</style>'
			. '<script id="ttcc-signage-pages">'
			. '(function(){function init(){'
			. 'var P=document.querySelectorAll(".page");if(P.length<2){return;}'
			// Rotate only once the sheet's fit pass has run: it measures each page,
			// and a page hidden before it is measured would come back unscaled.
			// Start anyway after 10s so a fit that never finishes still cycles.
			. 'var i=0,waited=0,t=setInterval(function(){'
			. 'if(document.documentElement.getAttribute("data-ttcc-fitted")==="1"||(waited+=200)>10000){'
			. 'clearInterval(t);show();setInterval(show,' . ( 20 * 1000 ) . ');}},200);'
			. 'function show(){for(var k=0;k<P.length;k++){P[k].style.display=(k===i)?"":"none";}'
			. 'i=(i+1)%P.length;}}'
			// This runs from <head>, so the pages do not exist yet.
			. 'if(document.readyState==="loading")'
			. '{document.addEventListener("DOMContentLoaded",init);}else{init();}})();'
			. '</script>';
	}
}
