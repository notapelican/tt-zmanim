<?php
/**
 * The two signage screens as bundles for the TT Luach.
 *
 * The Luach (the shul's Windows display app) downloads a zip per screen,
 * serves it from its own origin and frames it as a page in its rotation. It
 * refreshes the bundle's data files on its own cadence, so each bundle is a
 * small static loader plus dated data files:
 *
 *   sheet    index.html + loader.js + loader.css, and sheets/index.json with
 *            sheets/<sunday>.html for this week and the next two (the live
 *            signage HTML, as rendered for the wall).
 *   shabbos  index.html + board.css + board.js, and weeks/index.json with
 *            weeks/<sunday>.json for the same three weeks (the public
 *            shabbos-times JSON).
 *
 * The loaders pick the week by the current date in the site timezone, so a
 * kiosk that has been offline across a week boundary rolls over on its own
 * as long as it fetched next week's file while it could. The initial copies
 * inside the zip make a freshly installed kiosk correct before its first
 * refresh.
 *
 * Everything here is read-only and slug-gated like the signage pages
 * themselves; the descriptors are what the display plugin's luach feed
 * publishes (notapelican/ttcc-display, docs/luach-feed.md).
 *
 * @package TTCC_Zmanim
 */

defined( 'ABSPATH' ) || exit;

class TTCC_Zmanim_Bundle {

	const WEEKS        = 3;
	const CACHE_PREFIX = 'ttcc_bundle_';
	const CACHE_TTL    = 12 * HOUR_IN_SECONDS;

	public static function available() {
		return class_exists( 'ZipArchive' );
	}

	/** The Sundays covered: this week and the next WEEKS-1. */
	public static function sundays() {
		$out    = array();
		$sunday = TTCC_Zmanim_Public::current_sunday();
		for ( $i = 0; $i < self::WEEKS; $i++ ) {
			$d = date_create( $sunday );
			if ( ! $d ) {
				break;
			}
			$out[] = $d->modify( '+' . ( 7 * $i ) . ' days' )->format( 'Y-m-d' );
		}
		return $out;
	}

	/** True when $iso is a Sunday in the covered range (for the dated routes). */
	public static function covers( $iso ) {
		return in_array( $iso, self::sundays(), true );
	}

	private static function base_url( $slug ) {
		return home_url( '/ttcc-signage/' . rawurlencode( $slug ) . '/' );
	}

	/** The index both loaders read: which file covers which dates. */
	public static function index( $kind ) {
		$weeks = array();
		foreach ( self::sundays() as $sunday ) {
			$weeks[] = array(
				'sunday' => $sunday,
				'end'    => TTCC_Zmanim_Public::week_end( $sunday ),
				'file'   => $sunday . ( 'sheet' === $kind ? '.html' : '.json' ),
			);
		}
		return array(
			'generated_at' => current_datetime()->format( 'c' ),
			'tz'           => wp_timezone_string(),
			'weeks'        => $weeks,
		);
	}

	// --- the weekly sheet ------------------------------------------------------------

	/** The signage HTML for one week, as the wall shows it, with no self-refresh. */
	public static function sheet_html( $sunday ) {
		return TTCC_Zmanim_Public::signage_sheet_html( $sunday );
	}

	private static function sheet_loader_files() {
		$tz = wp_timezone_string();
		$index_html = '<!DOCTYPE html>' . "\n"
			. '<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">'
			. '<title>' . esc_html( get_bloginfo( 'name' ) ) . ' — ' . esc_html__( 'Times sheet', 'ttcc-zmanim' ) . '</title>'
			. '<link rel="stylesheet" href="loader.css"></head>'
			. '<body data-tz="' . esc_attr( $tz ) . '" data-index="sheets/index.json" data-dir="sheets/">'
			. '<iframe id="sheet" title="' . esc_attr__( 'This week\'s times', 'ttcc-zmanim' ) . '"></iframe>'
			. '<div id="status">' . esc_html__( 'Loading…', 'ttcc-zmanim' ) . '</div>'
			. '<script src="loader.js"></script></body></html>' . "\n";

		$css = "html,body{margin:0;padding:0;width:100%;height:100%;overflow:hidden;background:#fff}\n"
			. "#sheet{border:0;width:100%;height:100%;display:block}\n"
			. "#status{position:absolute;left:0;right:0;top:40vh;text-align:center;font:3vw system-ui,sans-serif;color:#444}\n"
			. "#status:empty{display:none}\n";

		$js = <<<'JS'
/*
 * Sheet loader: show the sheet whose week contains today.
 *
 * `sheets/index.json` lists the weeks on hand and the file for each; the
 * kiosk serving this bundle refreshes those files when it can. Today is taken
 * from the device clock in the site timezone, so a kiosk that was offline
 * across a week boundary moves to next week's sheet by itself. When today is
 * past every week on hand, the latest sheet stays up rather than a blank.
 */
(function () {
	'use strict';
	var body = document.body;
	var tz = body.getAttribute('data-tz') || undefined;
	var indexUrl = body.getAttribute('data-index') || 'sheets/index.json';
	var dir = body.getAttribute('data-dir') || 'sheets/';
	var frame = document.getElementById('sheet');
	var status = document.getElementById('status');
	var current = '';

	function today() {
		try {
			return new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
		} catch (e) {
			return new Date().toISOString().slice(0, 10);
		}
	}

	function pick(weeks) {
		var t = today(), i, best = null;
		for (i = 0; i < weeks.length; i++) {
			var w = weeks[i];
			if (w.sunday <= t && t <= w.end) { return w; }
			if (w.sunday <= t && (!best || w.sunday > best.sunday)) { best = w; }
		}
		return best || weeks[0] || null;
	}

	function load() {
		fetch(indexUrl, { cache: 'no-store' })
			.then(function (r) { if (!r.ok) { throw new Error('HTTP ' + r.status); } return r.json(); })
			.then(function (index) {
				var w = pick((index && index.weeks) || []);
				if (!w) { throw new Error('no weeks'); }
				var src = dir + w.file + '?v=' + encodeURIComponent(w.sunday);
				if (src !== current) {
					// Make sure the file is there before swapping, so a missing
					// week never replaces a sheet that is showing.
					return fetch(dir + w.file, { cache: 'no-store' }).then(function (r) {
						if (!r.ok) { throw new Error('HTTP ' + r.status); }
						current = src;
						frame.src = src;
						status.textContent = '';
					});
				}
				status.textContent = '';
			})
			.catch(function () {
				if (!current) { status.textContent = 'Times temporarily unavailable'; }
			});
	}

	load();
	setInterval(load, 60 * 60 * 1000);
})();
JS;
		return array(
			'index.html' => $index_html,
			'loader.css' => $css,
			'loader.js'  => $js . "\n",
		);
	}

	// --- the Shabbos board ------------------------------------------------------------

	/** The shabbos-times JSON for one week, or null. */
	public static function shabbos_week( $sunday ) {
		return TTCC_Zmanim_Shabbos::week_data( $sunday );
	}

	// --- files, zips, descriptors ------------------------------------------------------

	/** Every file for a bundle, path => contents, or WP_Error when nothing could be built. */
	public static function files( $kind ) {
		if ( 'sheet' === $kind ) {
			$files = self::sheet_loader_files();
			$files['sheets/index.json'] = wp_json_encode( self::index( 'sheet' ), JSON_UNESCAPED_UNICODE );
			$any = false;
			foreach ( self::sundays() as $sunday ) {
				$html = self::sheet_html( $sunday );
				if ( '' !== $html ) {
					$files[ 'sheets/' . $sunday . '.html' ] = $html;
					$any = true;
				}
			}
			if ( ! $any ) {
				return new WP_Error( 'ttcc_bundle_empty', 'No week could be rendered.' );
			}
			return $files;
		}
		if ( 'shabbos' === $kind ) {
			$files = TTCC_Zmanim_Shabbos::bundle_files();
			$files['weeks/index.json'] = wp_json_encode( self::index( 'shabbos' ), JSON_UNESCAPED_UNICODE );
			$any = false;
			foreach ( self::sundays() as $sunday ) {
				$week = self::shabbos_week( $sunday );
				if ( is_array( $week ) ) {
					$files[ 'weeks/' . $sunday . '.json' ] = wp_json_encode( $week, JSON_UNESCAPED_UNICODE );
					$any = true;
				}
			}
			if ( ! $any ) {
				return new WP_Error( 'ttcc_bundle_empty', 'No week could be fetched.' );
			}
			return $files;
		}
		return new WP_Error( 'ttcc_bundle_kind', 'Unknown bundle.' );
	}

	/**
	 * The loader's own version. The data files inside the zip change weekly
	 * but are refreshed separately; only a plugin update changes the loader,
	 * so a consumer re-downloads only then.
	 */
	public static function version( $kind ) {
		return TTCC_ZMANIM_VERSION . '-' . $kind;
	}

	/** Build (or fetch from cache) a bundle: array{version, sha256, bytes, zip} or WP_Error. */
	public static function build( $kind ) {
		if ( ! self::available() ) {
			return new WP_Error( 'ttcc_no_zip', 'PHP ZipArchive is not available on this server.' );
		}
		// Keyed by the week as well as the version: the initial data copies
		// inside the zip are this week's, and the sha256 the feed publishes
		// must be of the zip that is actually served.
		$key    = self::CACHE_PREFIX . $kind . '_' . md5( self::version( $kind ) . '|' . TTCC_Zmanim_Public::current_sunday() );
		$cached = get_transient( $key );
		if ( is_array( $cached ) && ! empty( $cached['zip'] ) ) {
			$cached['zip'] = base64_decode( $cached['zip'] ); // phpcs:ignore WordPress.PHP.DiscouragedPHPFunctions
			return $cached;
		}
		$files = self::files( $kind );
		if ( is_wp_error( $files ) ) {
			return $files;
		}
		$tmp = wp_tempnam( 'ttcc-bundle' );
		if ( ! $tmp ) {
			return new WP_Error( 'ttcc_tmp', 'Could not create a temporary file.' );
		}
		$za = new ZipArchive();
		if ( true !== $za->open( $tmp, ZipArchive::OVERWRITE ) ) {
			@unlink( $tmp ); // phpcs:ignore WordPress.PHP.NoSilencedErrors
			return new WP_Error( 'ttcc_zip', 'Could not open the zip for writing.' );
		}
		foreach ( $files as $path => $contents ) {
			$za->addFromString( $path, (string) $contents );
		}
		$za->close();
		$zip = (string) file_get_contents( $tmp ); // phpcs:ignore WordPress.WP.AlternativeFunctions
		@unlink( $tmp ); // phpcs:ignore WordPress.PHP.NoSilencedErrors

		$out = array(
			'version' => self::version( $kind ),
			'sha256'  => hash( 'sha256', $zip ),
			'bytes'   => strlen( $zip ),
			'zip'     => $zip,
		);
		set_transient( $key, array_merge( $out, array( 'zip' => base64_encode( $zip ) ) ), self::CACHE_TTL ); // phpcs:ignore WordPress.PHP.DiscouragedPHPFunctions
		return $out;
	}

	/** Descriptor for one bundle, or null when it cannot be built. */
	public static function descriptor( $kind, $slug ) {
		$built = self::build( $kind );
		if ( is_wp_error( $built ) ) {
			return null;
		}
		$base = self::base_url( $slug );
		$data = array();
		if ( 'sheet' === $kind ) {
			$data[] = array( 'path' => 'sheets/index.json', 'url' => $base . 'sheets/index.json', 'refresh' => 'daily', 'required' => true );
			foreach ( self::sundays() as $sunday ) {
				$data[] = array( 'path' => 'sheets/' . $sunday . '.html', 'url' => $base . 'sheets/' . $sunday . '.html', 'refresh' => 'daily', 'required' => false );
			}
		} else {
			$data[] = array( 'path' => 'weeks/index.json', 'url' => $base . 'weeks/index.json', 'refresh' => 'daily', 'required' => true );
			foreach ( self::sundays() as $sunday ) {
				$data[] = array( 'path' => 'weeks/' . $sunday . '.json', 'url' => $base . 'weeks/' . $sunday . '.json', 'refresh' => 'hourly', 'required' => false );
			}
		}
		return array(
			'key'         => 'sheet' === $kind ? 'ttcc-sheet' : 'ttcc-shabbos',
			'title'       => 'sheet' === $kind ? __( 'Weekly timesheet', 'ttcc-zmanim' ) : __( 'Shabbos & Yom Tov board', 'ttcc-zmanim' ),
			'kind'        => 'web',
			'entry'       => 'index.html',
			'zip_url'     => $base . 'bundle/' . $kind . '.zip',
			'version'     => $built['version'],
			'sha256'      => $built['sha256'],
			'bytes'       => $built['bytes'],
			// The sheet HTML carries the engine's own inline styles and fit
			// script, so a kiosk must allow inline code for that bundle.
			'csp'         => 'sheet' === $kind ? 'inline' : 'strict',
			'orientation' => 'sheet' === $kind ? 'any' : 'portrait',
			'seconds'     => 'sheet' === $kind ? 45 : 30,
			'data'        => $data,
		);
	}

	/** Both descriptors, for the display plugin's luach feed. */
	public static function descriptors() {
		$slug = TTCC_Zmanim_Settings::pisignage_slug();
		if ( ! $slug ) {
			return array();
		}
		$out = array();
		foreach ( array( 'sheet', 'shabbos' ) as $kind ) {
			$d = self::descriptor( $kind, $slug );
			if ( $d ) {
				$out[] = $d;
			}
		}
		return $out;
	}

	// --- serving ------------------------------------------------------------------------

	public static function serve_zip( $kind ) {
		$built = self::build( $kind );
		if ( is_wp_error( $built ) ) {
			status_header( 503 );
			nocache_headers();
			header( 'Content-Type: text/plain; charset=utf-8' );
			echo esc_html( $built->get_error_message() );
			return;
		}
		nocache_headers();
		header( 'Content-Type: application/zip' );
		header( 'Content-Length: ' . $built['bytes'] );
		header( 'Content-Disposition: attachment; filename="ttcc-' . $kind . '-' . $built['version'] . '.zip"' );
		header( 'X-TTCC-Bundle-Version: ' . $built['version'] );
		header( 'X-TTCC-Bundle-SHA256: ' . $built['sha256'] );
		echo $built['zip']; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- binary zip.
	}

	public static function serve_json( $data ) {
		if ( null === $data ) {
			status_header( 503 );
			nocache_headers();
			header( 'Content-Type: application/json; charset=utf-8' );
			echo wp_json_encode( array( 'error' => 'unavailable' ) );
			return;
		}
		nocache_headers();
		header( 'Content-Type: application/json; charset=utf-8' );
		echo wp_json_encode( $data, JSON_UNESCAPED_UNICODE ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- JSON.
	}

	public static function serve_html( $html ) {
		if ( '' === $html ) {
			status_header( 503 );
			nocache_headers();
			header( 'Content-Type: text/plain; charset=utf-8' );
			echo 'Times temporarily unavailable';
			return;
		}
		nocache_headers();
		header( 'Content-Type: text/html; charset=utf-8' );
		echo $html; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- self-contained service HTML.
	}
}
