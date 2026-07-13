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
		add_action( 'wp_enqueue_scripts', array( $this, 'enqueue' ) );
	}

	public function enqueue() {
		wp_register_style( 'ttcc-public', TTCC_ZMANIM_URL . 'public/css/public.css', array(), TTCC_ZMANIM_VERSION );
		wp_enqueue_style( 'ttcc-public' );
	}

	public static function add_rewrite_rules() {
		add_rewrite_rule( '^ttcc-signage/([^/]+)/?$', 'index.php?ttcc_signage=1&ttcc_slug=$matches[1]', 'top' );
	}

	public function query_vars( $vars ) {
		$vars[] = 'ttcc_signage';
		$vars[] = 'ttcc_slug';
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
	 * Returns HTML string, or '' if nothing (not even last-good) is available.
	 */
	public static function cached_html( $start, $end, $context = 'week', $inject_css = '' ) {
		$key    = self::LASTGOOD_KEY . md5( $context . '|' . $start . '|' . $end . '|' . $inject_css );
		$cached = get_transient( $key );
		if ( false !== $cached ) {
			return $cached;
		}

		$built = TTCC_Zmanim_Sheet::build( $start, $end, array() );
		if ( is_wp_error( $built ) ) {
			$lastgood = get_option( $key, '' );
			return $lastgood ? $lastgood : '';
		}
		$res = TTCC_Zmanim_Service_Client::render_html_doc( $built['doc'] );
		if ( is_wp_error( $res ) ) {
			$lastgood = get_option( $key, '' );
			return $lastgood ? $lastgood : '';
		}
		$html = $res['html'];
		if ( $inject_css ) {
			$html = self::inject_head( $html, $inject_css );
		}
		set_transient( $key, $html, self::CACHE_TTL );
		update_option( $key, $html, false ); // persistent last-good.
		return $html;
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

	public function maybe_render_signage() {
		if ( ! get_query_var( 'ttcc_signage' ) ) {
			return;
		}
		$slug = (string) get_query_var( 'ttcc_slug' );
		$want = TTCC_Zmanim_Settings::pisignage_slug();
		if ( ! $want || ! hash_equals( $want, $slug ) ) {
			status_header( 404 );
			nocache_headers();
			exit;
		}

		$sunday = self::current_sunday();
		$css    = self::signage_css();
		$html   = self::cached_html( $sunday, self::week_end( $sunday ), 'signage', $css );

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

	/** Large-type, high-contrast overrides for signage screens. */
	private static function signage_css() {
		return '<style id="ttcc-signage">'
			. 'html{background:#fff}'
			. 'body{zoom:1.6;max-width:none;margin:0 auto;padding:2vh 3vw}'
			. '.single{width:auto}'
			. '@media (min-width:1600px){body{zoom:2.1}}'
			. '</style>';
	}
}
