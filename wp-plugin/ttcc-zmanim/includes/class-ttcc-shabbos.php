<?php
/**
 * Shabbos & Yom Tov highlights surfaces: the [ttcc_shabbos] banner widget and
 * the piSignage "Shabbos screen" (/ttcc-signage/<slug>/shabbos/).
 *
 * All times come from the engine's /highlights endpoint (candle lighting,
 * Shabbos/Yom Tov ends, fast begin/end — the same assembled data as the
 * printed sheets); this class only caches and lays them out. Data is cached
 * per week (transient) with a persistent last-good fallback for the current
 * week, so a service outage never blanks the widget or the signage screen.
 *
 * @package TTCC_Zmanim
 */

defined( 'ABSPATH' ) || exit;

class TTCC_Zmanim_Shabbos {

	const CACHE_TTL    = 3 * HOUR_IN_SECONDS;
	const LASTGOOD_KEY = 'ttcc_shabbos_lastgood';
	/** Widget navigation window, days either side of today. */
	const WINDOW_DAYS  = 730;

	// --- data ----------------------------------------------------------------

	/** Snap any ISO date to its week's Sunday (site convention: Sun..Shabbos). */
	public static function sunday_of( $iso ) {
		$d = date_create( $iso );
		if ( ! $d ) {
			return '';
		}
		$dow = (int) $d->format( 'w' );
		$d->modify( '-' . $dow . ' days' );
		return $d->format( 'Y-m-d' );
	}

	/** True when $sunday_iso is inside the public navigation window. */
	public static function in_window( $sunday_iso ) {
		$d = date_create( $sunday_iso );
		if ( ! $d ) {
			return false;
		}
		$now  = current_datetime();
		$diff = abs( $d->getTimestamp() - $now->getTimestamp() ) / DAY_IN_SECONDS;
		return $diff <= self::WINDOW_DAYS;
	}

	/**
	 * Highlights data for the week of $sunday_iso (a Sunday), cached.
	 * Returns the week array (see engine/highlights.py) or null.
	 */
	public static function week_data( $sunday_iso ) {
		$current = TTCC_Zmanim_Public::current_sunday();
		$key     = 'ttcc_shabbos_' . $sunday_iso;
		$cached  = get_transient( $key );
		if ( false !== $cached && is_array( $cached ) ) {
			return $cached;
		}

		$set      = TTCC_Zmanim_Storage::get_active_profile_set();
		$profiles = $set && ! empty( $set['profiles'] ) ? $set['profiles'] : null;
		$notes    = $set && ! empty( $set['notes'] ) ? $set['notes'] : null;

		$end = TTCC_Zmanim_Public::week_end( $sunday_iso );
		$res = TTCC_Zmanim_Service_Client::highlights( $sunday_iso, $end, $profiles, $notes );
		if ( is_wp_error( $res ) || empty( $res['weeks'][0] ) ) {
			if ( $sunday_iso === $current ) {
				$lastgood = get_option( self::LASTGOOD_KEY, null );
				return is_array( $lastgood ) ? $lastgood : null;
			}
			return null;
		}
		$week = $res['weeks'][0];
		set_transient( $key, $week, self::CACHE_TTL );
		if ( $sunday_iso === $current ) {
			update_option( self::LASTGOOD_KEY, $week, false );
		}
		return $week;
	}

	/** REST callback (public, read-only): GET ttcc/v1/shabbos-times[?week=YYYY-MM-DD]. */
	public static function rest_week( $request ) {
		$week = (string) $request->get_param( 'week' );
		if ( '' !== $week && ! preg_match( '/^\d{4}-\d{2}-\d{2}$/', $week ) ) {
			return new WP_Error( 'ttcc_bad_week', __( 'week must be a YYYY-MM-DD date', 'ttcc-zmanim' ), array( 'status' => 400 ) );
		}
		$sunday = '' === $week ? TTCC_Zmanim_Public::current_sunday() : self::sunday_of( $week );
		if ( ! $sunday || ! self::in_window( $sunday ) ) {
			return new WP_Error( 'ttcc_out_of_range', __( 'week is outside the available range', 'ttcc-zmanim' ), array( 'status' => 400 ) );
		}
		$data = self::week_data( $sunday );
		if ( null === $data ) {
			return new WP_Error( 'ttcc_unavailable', __( 'Times are temporarily unavailable.', 'ttcc-zmanim' ), array( 'status' => 503 ) );
		}
		return rest_ensure_response( $data );
	}

	/** JSON for safe embedding inside <script> tags. */
	private static function json( $data ) {
		return wp_json_encode( $data, JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_AMP );
	}

	private static function rest_endpoint() {
		return rest_url( 'ttcc/v1/shabbos-times' );
	}

	// --- [ttcc_shabbos] widget ------------------------------------------------

	/**
	 * Shared client-side renderer: turns a highlights week dict into rows.
	 * Used verbatim by both the widget and the signage screen.
	 */
	private static function render_js_helpers() {
		return <<<'JS'
function ttccFmtTime(hm) {
	var p = String(hm || '').split(':');
	var h = parseInt(p[0], 10), m = p[1] || '00';
	if (isNaN(h)) return hm;
	var ap = h < 12 ? 'am' : 'pm';
	h = h % 12; if (h === 0) h = 12;
	return h + ':' + m + ap;
}
function ttccEsc(s) {
	return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
		return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
	});
}
JS;
	}

	/** [ttcc_shabbos] — Shabbos & Yom Tov times banner with week navigation. */
	public static function shortcode_widget( $atts ) {
		$atts = shortcode_atts(
			array(
				'location' => 'Bondi · Sydney NSW',
				'footer'   => __( "According to the Alter Rebbe's Zmanim — Tzemach Tzedek Community Centre", 'ttcc-zmanim' ),
				'nav'      => 'yes',
			),
			$atts,
			'ttcc_shabbos'
		);

		$sunday  = TTCC_Zmanim_Public::current_sunday();
		$initial = self::week_data( $sunday );
		$uid     = 'stw-' . wp_unique_id();
		$cfg     = array(
			'rest'    => self::rest_endpoint(),
			'sunday'  => $sunday,
			'nav'     => 'yes' === $atts['nav'],
			'initial' => $initial,
		);

		ob_start();
		self::widget_css();
		?>
<div class="ttcc-stw" id="<?php echo esc_attr( $uid ); ?>" aria-live="polite">
	<div class="stw-card">
		<div class="stw-topbar">
			<div class="stw-eyebrow"><?php echo esc_html( $atts['location'] ); ?></div>
			<?php if ( 'yes' === $atts['nav'] ) : ?>
			<nav class="stw-nav" aria-label="<?php esc_attr_e( 'Change week', 'ttcc-zmanim' ); ?>">
				<button type="button" class="stw-btn stw-prev" aria-label="<?php esc_attr_e( 'Previous week', 'ttcc-zmanim' ); ?>">&lsaquo; <?php esc_html_e( 'Prev', 'ttcc-zmanim' ); ?></button>
				<button type="button" class="stw-btn stw-btn-now stw-today"><?php esc_html_e( 'This Week', 'ttcc-zmanim' ); ?></button>
				<button type="button" class="stw-btn stw-next" aria-label="<?php esc_attr_e( 'Next week', 'ttcc-zmanim' ); ?>"><?php esc_html_e( 'Next', 'ttcc-zmanim' ); ?> &rsaquo;</button>
				<label class="stw-jump">
					<span class="stw-jump-label"><?php esc_html_e( 'Jump to', 'ttcc-zmanim' ); ?></span>
					<input type="date" class="stw-date" aria-label="<?php esc_attr_e( 'Jump to a date', 'ttcc-zmanim' ); ?>">
				</label>
			</nav>
			<?php endif; ?>
		</div>

		<div class="stw-horizon" role="presentation"></div>

		<div class="stw-main">
			<header class="stw-ident">
				<h2 class="stw-title"><?php esc_html_e( 'Loading…', 'ttcc-zmanim' ); ?></h2>
				<div class="stw-hebrew"></div>
				<div class="stw-range"></div>
				<div class="stw-chips"></div>
			</header>
			<div class="stw-timeswrap">
				<ul class="stw-times"></ul>
				<div class="stw-status"><?php esc_html_e( 'Fetching times…', 'ttcc-zmanim' ); ?></div>
			</div>
		</div>

		<footer class="stw-foot"><?php echo esc_html( $atts['footer'] ); ?></footer>
	</div>
</div>
<script type="application/json" class="ttcc-stw-config"><?php echo self::json( $cfg ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- JSON_HEX_TAG-encoded. ?></script>
		<?php
		self::widget_js();
		return ob_get_clean();
	}

	/** Widget CSS, printed once per page. */
	private static function widget_css() {
		static $done = false;
		if ( $done ) {
			return;
		}
		$done = true;
		?>
<style id="ttcc-stw-css">
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700&family=Assistant:wght@400;600;700&display=swap');
.ttcc-stw{--stw-night:#141d33;--stw-night-2:#1c2947;--stw-flame:#e3a83b;--stw-rose:#c96a5a;--stw-paper:#f6f2e9;--stw-muted:#9aa5c0;--stw-line:rgba(246,242,233,.12);font-family:'Assistant',system-ui,-apple-system,sans-serif;width:100%;max-width:1250px;margin:0 auto}
.ttcc-stw .stw-card{background:linear-gradient(105deg,var(--stw-night-2) 0%,var(--stw-night) 60%);color:var(--stw-paper);border-radius:16px;padding:28px 36px 18px;box-shadow:0 10px 32px rgba(10,16,34,.35)}
.ttcc-stw .stw-topbar{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px}
.ttcc-stw .stw-eyebrow{font-size:12px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:var(--stw-flame)}
.ttcc-stw .stw-nav{display:flex;align-items:center;flex-wrap:wrap;gap:8px}
.ttcc-stw .stw-btn{font:600 13px 'Assistant',sans-serif;color:var(--stw-paper);background:transparent;border:1px solid var(--stw-line);border-radius:8px;padding:7px 13px;cursor:pointer;transition:border-color .15s,color .15s}
.ttcc-stw .stw-btn:hover,.ttcc-stw .stw-btn:focus-visible{border-color:var(--stw-flame);color:var(--stw-flame);outline:none}
.ttcc-stw .stw-btn-now{border-color:var(--stw-flame);color:var(--stw-flame)}
.ttcc-stw .stw-jump{display:flex;align-items:center;gap:6px;margin-left:6px}
.ttcc-stw .stw-jump-label{font-size:12px;color:var(--stw-muted)}
.ttcc-stw .stw-jump input{font:600 12px 'Assistant',sans-serif;color:var(--stw-paper);background:transparent;border:1px solid var(--stw-line);border-radius:8px;padding:5px 8px;color-scheme:dark;max-width:145px}
.ttcc-stw .stw-horizon{height:3px;border-radius:2px;margin:16px 0 22px;background:linear-gradient(90deg,var(--stw-flame) 0%,var(--stw-rose) 35%,transparent 90%)}
.ttcc-stw .stw-main{display:grid;grid-template-columns:minmax(280px,380px) 1fr;gap:20px 44px;align-items:start}
.ttcc-stw .stw-title{font-family:'Montserrat','Assistant',system-ui,sans-serif;font-weight:700;font-size:32px;line-height:1.15;margin:0 0 4px;color:var(--stw-paper)}
.ttcc-stw .stw-hebrew{font-family:'Montserrat','Assistant',system-ui,sans-serif;font-size:19px;color:var(--stw-flame);min-height:1em}
.ttcc-stw .stw-range{font-size:13.5px;color:var(--stw-muted);margin-top:8px}
.ttcc-stw .stw-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.ttcc-stw .stw-chip{font-size:12px;font-weight:600;padding:3px 10px;border:1px solid var(--stw-line);border-radius:999px;color:var(--stw-muted)}
.ttcc-stw .stw-chip.fast{border-color:var(--stw-rose);color:var(--stw-rose)}
.ttcc-stw .stw-times{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:14px}
.ttcc-stw .stw-row{flex:1 1 200px;max-width:280px;border:1px solid var(--stw-line);border-radius:12px;padding:16px 18px;background:rgba(246,242,233,.03);margin:0}
.ttcc-stw .stw-label{font-weight:700;font-size:15px}
.ttcc-stw .stw-memo{font-size:12px;color:var(--stw-flame);font-weight:600;margin-top:1px}
.ttcc-stw .stw-row.fast .stw-memo{color:var(--stw-rose)}
.ttcc-stw .stw-day{font-size:12.5px;color:var(--stw-muted);margin-top:3px}
.ttcc-stw .stw-time{font-family:'Montserrat','Assistant',system-ui,sans-serif;font-size:30px;font-weight:700;color:var(--stw-flame);white-space:nowrap;margin-top:8px}
.ttcc-stw .stw-row.fast .stw-time{color:var(--stw-rose)}
.ttcc-stw .stw-qual{display:block;font-family:'Assistant',sans-serif;font-size:12px;font-weight:600;color:var(--stw-muted);text-transform:lowercase}
.ttcc-stw .stw-status{font-size:13px;color:var(--stw-muted);padding:8px 0}
.ttcc-stw .stw-status:empty{display:none}
.ttcc-stw .stw-foot{font-size:11px;color:var(--stw-muted);margin-top:22px;padding-top:12px;border-top:1px solid var(--stw-line)}
@media (max-width:900px){.ttcc-stw .stw-main{grid-template-columns:1fr;gap:18px}.ttcc-stw .stw-title{font-size:27px}.ttcc-stw .stw-row{max-width:none}}
@media (max-width:560px){.ttcc-stw .stw-card{padding:20px 18px 14px;border-radius:12px}.ttcc-stw .stw-topbar{flex-direction:column;align-items:flex-start}.ttcc-stw .stw-nav{width:100%}.ttcc-stw .stw-btn{flex:1 1 0;padding:9px 6px;text-align:center}.ttcc-stw .stw-jump{margin-left:0;width:100%}.ttcc-stw .stw-jump input{flex:1;max-width:none}.ttcc-stw .stw-title{font-size:23px}.ttcc-stw .stw-times{flex-direction:column;gap:0}.ttcc-stw .stw-row{flex:none;display:flex;align-items:baseline;justify-content:space-between;gap:12px;border:none;border-bottom:1px solid var(--stw-line);border-radius:0;background:none;padding:13px 2px}.ttcc-stw .stw-row:last-child{border-bottom:none}.ttcc-stw .stw-time{font-size:22px;margin-top:0}}
</style>
		<?php
	}

	/** Widget JS, printed once per page; initializes every .ttcc-stw instance. */
	private static function widget_js() {
		static $done = false;
		if ( $done ) {
			return;
		}
		$done = true;
		?>
<script id="ttcc-stw-js">
(function () {
	'use strict';
	<?php echo self::render_js_helpers(); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- static JS. ?>

	function rowsHtml(week) {
		return (week.items || []).map(function (it) {
			var fast = it.kind === 'fast_begins' || it.kind === 'fast_ends';
			return '<li class="stw-row' + (fast ? ' fast' : '') + '"><div>'
				+ '<div class="stw-label">' + ttccEsc(it.label) + '</div>'
				+ (it.memo ? '<div class="stw-memo">' + ttccEsc(it.memo) + '</div>' : '')
				+ '<div class="stw-day">' + ttccEsc(it.day_display) + '</div>'
				+ '</div><div class="stw-time">'
				+ (it.qualifier ? '<span class="stw-qual">' + ttccEsc(it.qualifier) + '</span>' : '')
				+ ttccEsc(ttccFmtTime(it.time)) + '</div></li>';
		}).join('');
	}

	function initWidget(root, cfg) {
		var q = function (sel) { return root.querySelector(sel); };
		var sunday = cfg.sunday;
		var seq = 0;

		function render(week) {
			q('.stw-title').textContent = week.title || 'Shabbos times';
			q('.stw-hebrew').textContent = week.hebrew_dates || '';
			q('.stw-range').textContent = week.range_display || '';
			q('.stw-chips').innerHTML = (week.chips || []).map(function (c) {
				return '<span class="stw-chip' + (c.kind === 'fast' ? ' fast' : '') + '">' + ttccEsc(c.text) + '</span>';
			}).join('');
			var rows = rowsHtml(week);
			q('.stw-times').innerHTML = rows;
			q('.stw-status').textContent = rows ? '' : 'No times found for this week.';
		}

		function load(target) {
			var mySeq = ++seq;
			q('.stw-status').textContent = 'Fetching times…';
			var url = cfg.rest + (cfg.rest.indexOf('?') === -1 ? '?' : '&') + 'week=' + encodeURIComponent(target);
			fetch(url)
				.then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
				.then(function (week) {
					if (mySeq !== seq) return;
					sunday = week.civil_start || target;
					syncPicker();
					render(week);
				})
				.catch(function () {
					if (mySeq !== seq) return;
					q('.stw-status').textContent = 'Couldn’t load times for that week.';
					q('.stw-times').innerHTML = '';
				});
		}

		function shiftDays(iso, days) {
			var p = iso.split('-');
			var d = new Date(Date.UTC(+p[0], +p[1] - 1, +p[2] + days));
			return d.toISOString().slice(0, 10);
		}

		function syncPicker() {
			var input = q('.stw-date');
			if (input) input.value = sunday;
		}

		if (cfg.nav) {
			q('.stw-prev').addEventListener('click', function () { load(shiftDays(sunday, -7)); });
			q('.stw-next').addEventListener('click', function () { load(shiftDays(sunday, 7)); });
			q('.stw-today').addEventListener('click', function () { load(cfg.sunday); });
			q('.stw-date').addEventListener('change', function () {
				if (this.value) load(this.value);
			});
			syncPicker();
		}

		if (cfg.initial) {
			render(cfg.initial);
		} else {
			load(sunday);
		}
	}

	function scan() {
		document.querySelectorAll('script.ttcc-stw-config').forEach(function (tag) {
			var cfg;
			try { cfg = JSON.parse(tag.textContent); } catch (e) { return; }
			var root = tag.previousElementSibling;
			if (root && root.classList.contains('ttcc-stw') && !root.dataset.ttccInit) {
				root.dataset.ttccInit = '1';
				initWidget(root, cfg);
			}
		});
	}
	scan();
	// The script prints once, right after the FIRST instance — later
	// instances on the same page are picked up when the DOM is complete.
	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', scan);
	}
})();
</script>
		<?php
	}

	// --- piSignage Shabbos screen ----------------------------------------------

	/**
	 * Full-page portrait signage screen (1080x1920-first, vh-scaled) for the
	 * current week. Non-interactive, self-refreshing (re-fetches every 3 hours,
	 * retries every 5 minutes after a failure, keeps stale data offline).
	 * Echoes a complete HTML document.
	 */
	public static function render_signage_screen() {
		$sunday = TTCC_Zmanim_Public::current_sunday();
		$week   = self::week_data( $sunday );
		$cfg    = array(
			'rest'      => self::rest_endpoint(),
			'initial'   => $week,
			'refreshMs' => 3 * HOUR_IN_SECONDS * 1000,
			'retryMs'   => 5 * MINUTE_IN_SECONDS * 1000,
			'tz'        => wp_timezone_string(),
		);
		$site  = wp_parse_url( home_url(), PHP_URL_HOST );
		$title = get_bloginfo( 'name' );
		?>
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title><?php echo esc_html( $title ); ?> — <?php esc_html_e( 'Shabbos Times', 'ttcc-zmanim' ); ?></title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700&family=Assistant:wght@400;600;700&display=swap" rel="stylesheet">
<style>
	:root{--night:#141d33;--night-2:#1c2947;--flame:#e3a83b;--rose:#c96a5a;--paper:#f6f2e9;--muted:#9aa5c0;--line:rgba(246,242,233,.14)}
	*{margin:0;padding:0;box-sizing:border-box}
	html,body{width:100%;height:100%;overflow:hidden}
	body{font-family:'Assistant',system-ui,sans-serif;color:var(--paper);background:radial-gradient(140% 100% at 50% 0%,var(--night-2) 0%,var(--night) 60%);display:flex;flex-direction:column;padding:4vh 6vw 2.5vh}
	.topbar{display:flex;justify-content:space-between;align-items:baseline}
	.eyebrow{font-size:1.9vh;font-weight:700;letter-spacing:.2em;text-transform:uppercase;color:var(--flame)}
	.clock{text-align:right}
	.clock-time{font-family:'Montserrat','Assistant',system-ui,sans-serif;font-size:3vh;font-weight:500}
	.clock-date{font-size:1.6vh;color:var(--muted)}
	.horizon{height:.4vh;border-radius:1vh;margin:2.2vh 0 3vh;background:linear-gradient(90deg,var(--flame) 0%,var(--rose) 45%,transparent 95%)}
	.title{font-family:'Montserrat','Assistant',system-ui,sans-serif;font-weight:700;font-size:6.2vh;line-height:1.12}
	.hebrew{font-family:'Montserrat','Assistant',system-ui,sans-serif;font-size:3.4vh;color:var(--flame);min-height:1em}
	.range{font-size:2vh;color:var(--muted);margin-top:.8vh}
	.chips{display:flex;flex-wrap:wrap;gap:1vh;margin-top:1.4vh;list-style:none}
	.chip{font-size:1.8vh;font-weight:600;padding:.5vh 1.8vh;border:1px solid var(--line);border-radius:99px;color:var(--muted)}
	.chip.fast{border-color:var(--rose);color:var(--rose)}
	/* Rows are em-sized against .times so the fit loop below can scale a busy
	   chag week (6+ rows) down to the space left under the identity block. */
	.times{list-style:none;display:flex;flex-direction:column;justify-content:center;gap:.7em;flex:1;margin-top:3vh;min-height:0;overflow:hidden;font-size:3vh}
	.row{display:flex;align-items:center;justify-content:space-between;gap:3vw;border-radius:1.6vh;padding:.8em 3.6vw;background:rgba(246,242,233,.035)}
	.label{font-weight:700;font-size:1em;line-height:1.2}
	.memo{font-size:.67em;color:var(--flame);font-weight:600;margin-top:.1em}
	.row.fast .memo{color:var(--rose)}
	.day{font-size:.67em;color:var(--muted);margin-top:.17em}
	.time{font-family:'Montserrat','Assistant',system-ui,sans-serif;font-size:2.13em;font-weight:700;color:var(--flame);white-space:nowrap;text-align:right}
	.row.fast .time{color:var(--rose)}
	.qual{display:block;font-family:'Assistant',sans-serif;font-size:.63em;font-weight:600;color:var(--muted);text-transform:lowercase}
	.status{font-size:2.2vh;color:var(--muted)}
	.status:empty{display:none}
	.cta{text-align:center;font-size:2.2vh;font-weight:600;color:var(--paper);padding:1.8vh 0;margin-top:1.5vh;border-top:1px solid var(--line)}
	.cta .site{font-family:'Montserrat','Assistant',system-ui,sans-serif;font-size:2.8vh;font-weight:700;color:var(--flame);letter-spacing:.03em}
	.foot{font-size:1.5vh;color:var(--muted);padding-top:1.4vh;border-top:1px solid var(--line);text-align:center}
</style>
</head>
<body>
	<div class="topbar">
		<div class="eyebrow"><?php echo esc_html( apply_filters( 'ttcc_shabbos_signage_location', 'Bondi · Sydney NSW' ) ); ?></div>
		<div class="clock">
			<div class="clock-time" id="clock-time">&nbsp;</div>
			<div class="clock-date" id="clock-date">&nbsp;</div>
		</div>
	</div>
	<div class="horizon"></div>
	<div class="ident">
		<h1 class="title" id="title"><?php esc_html_e( 'Shabbos Times', 'ttcc-zmanim' ); ?></h1>
		<div class="hebrew" id="hebrew"></div>
		<div class="range" id="range"></div>
		<ul class="chips" id="chips"></ul>
	</div>
	<ul class="times" id="times"></ul>
	<div class="status" id="status"><?php esc_html_e( 'Loading times…', 'ttcc-zmanim' ); ?></div>
	<div class="cta"><?php esc_html_e( 'For zmanim & community updates visit', 'ttcc-zmanim' ); ?> <span class="site"><?php echo esc_html( $site ); ?></span></div>
	<div class="foot"><?php echo esc_html( apply_filters( 'ttcc_shabbos_signage_footer', "Times for Bondi, NSW · According to the Alter Rebbe's Zmanim — Tzemach Tzedek Community Centre" ) ); ?></div>

<script type="application/json" id="stw-config"><?php echo self::json( $cfg ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- JSON_HEX_TAG-encoded. ?></script>
<script>
(function () {
	'use strict';
	<?php echo self::render_js_helpers(); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- static JS. ?>

	var cfg = JSON.parse(document.getElementById('stw-config').textContent);
	var els = {
		title: document.getElementById('title'),
		hebrew: document.getElementById('hebrew'),
		range: document.getElementById('range'),
		chips: document.getElementById('chips'),
		times: document.getElementById('times'),
		status: document.getElementById('status'),
		clockTime: document.getElementById('clock-time'),
		clockDate: document.getElementById('clock-date')
	};

	function render(week) {
		els.title.textContent = week.title || 'Shabbos Times';
		els.hebrew.textContent = week.hebrew_dates || '';
		els.range.textContent = week.range_display || '';
		els.chips.innerHTML = (week.chips || []).map(function (c) {
			return '<li class="chip' + (c.kind === 'fast' ? ' fast' : '') + '">' + ttccEsc(c.text) + '</li>';
		}).join('');
		var count = 0;
		var rows = (week.items || []).map(function (it) {
			count++;
			var fast = it.kind === 'fast_begins' || it.kind === 'fast_ends';
			return '<li class="row' + (fast ? ' fast' : '') + '"><div>'
				+ '<div class="label">' + ttccEsc(it.label) + '</div>'
				+ (it.memo ? '<div class="memo">' + ttccEsc(it.memo) + '</div>' : '')
				+ '<div class="day">' + ttccEsc(it.day_display) + '</div>'
				+ '</div><div class="time">'
				+ (it.qualifier ? '<span class="qual">' + ttccEsc(it.qualifier) + '</span>' : '')
				+ ttccEsc(ttccFmtTime(it.time)) + '</div></li>';
		}).join('');
		els.times.innerHTML = rows;
		els.status.textContent = rows ? '' : 'No times found this week.';
		fitRows();
	}

	// Shrink the row type until every row fits in the space under the
	// identity block (busy chag weeks can carry 6+ rows).
	function fitRows() {
		els.times.style.fontSize = '';
		requestAnimationFrame(function () {
			var size = 3.0; // vh — matches the stylesheet default
			var guard = 0;
			while (els.times.scrollHeight > els.times.clientHeight + 1 && size > 1.2 && guard++ < 24) {
				size -= 0.1;
				els.times.style.fontSize = size.toFixed(2) + 'vh';
			}
		});
	}
	window.addEventListener('resize', fitRows);

	var retryTimer = null;
	function load() {
		fetch(cfg.rest)
			.then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
			.then(function (week) {
				if (retryTimer) { clearTimeout(retryTimer); retryTimer = null; }
				render(week);
			})
			.catch(function () {
				// Stale beats blank on signage; only show a message if
				// nothing has ever rendered.
				if (!els.times.innerHTML) {
					els.status.textContent = 'Waiting for connection…';
				}
				retryTimer = setTimeout(load, cfg.retryMs);
			});
	}

	// Clock in the SITE timezone (the signage device may run UTC).
	var timeFmt, dateFmt;
	try {
		timeFmt = new Intl.DateTimeFormat('en-AU', { hour: 'numeric', minute: '2-digit', hour12: true, timeZone: cfg.tz });
		dateFmt = new Intl.DateTimeFormat('en-AU', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: cfg.tz });
	} catch (e) {
		timeFmt = new Intl.DateTimeFormat('en-AU', { hour: 'numeric', minute: '2-digit', hour12: true });
		dateFmt = new Intl.DateTimeFormat('en-AU', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
	}
	function tickClock() {
		var now = new Date();
		els.clockTime.textContent = timeFmt.format(now).replace(/\s/g, '');
		els.clockDate.textContent = dateFmt.format(now);
	}

	tickClock();
	setInterval(tickClock, 1000);
	if (cfg.initial) { render(cfg.initial); } else { load(); }
	setInterval(load, cfg.refreshMs);
})();
</script>
</body>
</html>
		<?php
	}
}
