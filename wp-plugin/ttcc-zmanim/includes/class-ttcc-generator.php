<?php
/**
 * Front-end ("clergy") timesheet generator: the [ttcc_generator] shortcode, the
 * public routes it calls, and its export handler.
 *
 * Deliberately narrower than the wp-admin dashboard. A clergy member picks a
 * week (or a run of weeks), optionally adjusts minyan times / adds lines and
 * notes, and exports a PDF, an image, or the WhatsApp broadcast text. Styling is
 * NOT exposed: every sheet is rendered with the site's house design (the default
 * style preset, else the Settings > Modern layout defaults), and the only choice
 * is Classic (the default) or Modern.
 *
 * Times stay the engine's. Like the admin dashboard, this class only forwards
 * line/note overrides to the service and never computes or re-rounds a time.
 *
 * Overrides saved in wp-admin for the same weeks are merged in UNDERNEATH the
 * visitor's own edits (both are block-scoped, so only the shown weeks apply), so
 * a front-end sheet reflects the corrections the shul already published.
 *
 * Trust model: the routes are reachable by any visitor who can see the page
 * (Settings > Clergy generator can require a login instead), so requests are
 * validated field by field, range-capped, throttled per IP, and stripped of any
 * design keys. Nothing here writes to the timesheet archive.
 *
 * @package TTCC_Zmanim
 */

defined( 'ABSPATH' ) || exit;

class TTCC_Zmanim_Generator {

	const SHORTCODE     = 'ttcc_generator';
	const EXPORT_ACTION = 'ttcc_gen_export';
	const EXPORT_NONCE  = 'ttcc_gen_export';

	/** Hard caps on what a front-end visitor may ask the engine for. */
	// 6 covers a whole Tishrei (Erev Rosh Hashana through Shabbos Bereishis).
	const MAX_WEEKS   = 6;
	const WINDOW_DAYS = 730;

	/** Rendered-sheet cache (unedited sheets only). */
	const CACHE_TTL = 30 * MINUTE_IN_SECONDS;

	/** Per-IP throttle: builds (preview / WhatsApp), file exports, and in-page
	 * image views per window. Viewing has its own budget so browsing the share
	 * shapes on screen can never use up the download allowance. */
	const THROTTLE_WINDOW = 600;
	const THROTTLE_BUILD  = 150;
	const THROTTLE_EXPORT = 30;
	const THROTTLE_VIEW   = 60;

	/** Override-payload caps (a normal sheet uses a handful of each). */
	const MAX_LINE_EDITS  = 200;
	const MAX_NOTE_BLOCKS = 60;
	const MAX_ADDED_NOTES = 12;

	// --- wiring ---------------------------------------------------------------

	public function hooks() {
		add_shortcode( self::SHORTCODE, array( __CLASS__, 'shortcode' ) );
		add_action( 'wp_enqueue_scripts', array( __CLASS__, 'register_assets' ) );
		add_action( 'wp_ajax_' . self::EXPORT_ACTION, array( __CLASS__, 'handle_export' ) );
		add_action( 'wp_ajax_nopriv_' . self::EXPORT_ACTION, array( __CLASS__, 'handle_export' ) );
	}

	public function register_routes() {
		$perm = array( __CLASS__, 'can_use' );

		register_rest_route( TTCC_Zmanim_REST::NS, '/generator/preview', array(
			'methods'             => 'POST',
			'callback'            => array( __CLASS__, 'rest_preview' ),
			'permission_callback' => $perm,
		) );

		register_rest_route( TTCC_Zmanim_REST::NS, '/generator/whatsapp', array(
			'methods'             => 'POST',
			'callback'            => array( __CLASS__, 'rest_whatsapp' ),
			'permission_callback' => $perm,
		) );
	}

	// --- access ---------------------------------------------------------------

	/**
	 * Who may generate from the front end. 'open' (default) = anyone who can see
	 * the page; 'logged_in' = signed-in users; 'off' = nobody but timesheet
	 * managers (so an admin can still preview the page).
	 */
	public static function can_use() {
		if ( current_user_can( TTCC_ZMANIM_CAP ) ) {
			return true;
		}
		$mode = TTCC_Zmanim_Settings::generator_access();
		if ( 'off' === $mode ) {
			return false;
		}
		if ( 'logged_in' === $mode ) {
			return is_user_logged_in();
		}
		return true;
	}

	public static function register_assets() {
		wp_register_style(
			'ttcc-generator-fonts',
			'https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700&family=Assistant:wght@400;600;700&display=swap',
			array(),
			null // phpcs:ignore WordPress.WP.EnqueuedResourceParameters.MissingVersion -- Google Fonts URL is versioned by its query args.
		);
		wp_register_style( 'ttcc-generator', TTCC_ZMANIM_URL . 'public/css/generator.css', array( 'ttcc-generator-fonts' ), TTCC_ZMANIM_VERSION );
		wp_register_script( 'ttcc-generator', TTCC_ZMANIM_URL . 'public/js/generator.js', array(), TTCC_ZMANIM_VERSION, true );
	}

	// --- shortcode ------------------------------------------------------------

	/**
	 * [ttcc_generator] — the generator UI.
	 *
	 * Attributes: title, eyebrow, footer, weeks (initial 1..MAX_WEEKS),
	 * style (classic|modern initial choice).
	 */
	public static function shortcode( $atts ) {
		$atts = shortcode_atts(
			array(
				'title'   => __( 'Timesheet generator', 'ttcc-zmanim' ),
				'eyebrow' => __( 'Tzemach Tzedek Community Centre', 'ttcc-zmanim' ),
				'footer'  => __( "Times are calculated by the TTCC zmanim engine according to the Alter Rebbe's zmanim. Check the sheet before it is published.", 'ttcc-zmanim' ),
				'weeks'   => '1',
				'style'   => 'classic',
			),
			$atts,
			self::SHORTCODE
		);

		if ( ! self::can_use() ) {
			return '<div class="ttcc-gen-notice">' . esc_html__( 'The timesheet generator is available to signed-in shul staff.', 'ttcc-zmanim' ) . '</div>';
		}

		wp_enqueue_style( 'ttcc-generator' );
		wp_enqueue_script( 'ttcc-generator' );

		$uid   = 'ttcc-gen-' . wp_unique_id();
		$weeks = max( 1, min( self::MAX_WEEKS, (int) $atts['weeks'] ) );
		$cfg   = array(
			'id'           => $uid,
			'restUrl'      => esc_url_raw( rest_url( TTCC_Zmanim_REST::NS . '/generator' ) ),
			'ajaxUrl'      => esc_url_raw( admin_url( 'admin-ajax.php' ) ),
			'exportAction' => self::EXPORT_ACTION,
			// Nonces are only useful for signed-in visitors: an anonymous page view
			// may be served from a page cache with a stale nonce, and WordPress
			// rejects a REST request that carries an invalid one. These routes are
			// public and read-only, so anonymous callers simply send no nonce.
			'nonce'        => is_user_logged_in() ? wp_create_nonce( 'wp_rest' ) : '',
			'exportNonce'  => is_user_logged_in() ? wp_create_nonce( self::EXPORT_NONCE ) : '',
			'sunday'       => TTCC_Zmanim_Public::current_sunday(),
			'weeks'        => $weeks,
			'template'     => 'modern' === $atts['style'] ? 'modern' : 'classic',
			'i18n'         => self::i18n(),
		);

		ob_start();
		?>
<div class="ttcc-gen" id="<?php echo esc_attr( $uid ); ?>">
	<div class="tg-card">
		<header class="tg-head">
			<div>
				<?php if ( $atts['eyebrow'] ) : ?>
					<p class="tg-eyebrow"><?php echo esc_html( $atts['eyebrow'] ); ?></p>
				<?php endif; ?>
				<h2 class="tg-title"><?php echo esc_html( $atts['title'] ); ?></h2>
			</div>
			<div class="tg-summary" data-role="summary" role="status" aria-live="polite"></div>
		</header>

		<section class="tg-wa" data-role="wa" hidden aria-label="<?php esc_attr_e( 'WhatsApp broadcast text', 'ttcc-zmanim' ); ?>">
			<div class="tg-wa-head">
				<h3 class="tg-wa-title"><?php esc_html_e( 'WhatsApp broadcast', 'ttcc-zmanim' ); ?></h3>
				<span class="tg-status" data-role="wa-status" role="status" aria-live="polite"></span>
				<span class="tg-spacer"></span>
				<button type="button" class="tg-wa-btn" data-role="wa-copy"><?php esc_html_e( 'Copy text', 'ttcc-zmanim' ); ?></button>
				<a class="tg-mini" data-role="wa-open" href="#" target="_blank" rel="noopener noreferrer" hidden><?php esc_html_e( 'Open in WhatsApp', 'ttcc-zmanim' ); ?></a>
				<button type="button" class="tg-mini" data-role="wa-close"><?php esc_html_e( 'Close', 'ttcc-zmanim' ); ?></button>
			</div>
			<textarea class="tg-wa-text" data-role="wa-text" rows="16" spellcheck="false"></textarea>
			<p class="tg-wa-hint"><?php esc_html_e( 'Essential minyan times only. Paste into WhatsApp — the *asterisks* become bold.', 'ttcc-zmanim' ); ?></p>
		</section>

		<div class="tg-body">
			<div class="tg-side">

			<div class="tg-controls">
				<div class="tg-field">
					<span class="tg-label" id="<?php echo esc_attr( $uid ); ?>-wk"><?php esc_html_e( 'Week beginning (Sunday)', 'ttcc-zmanim' ); ?></span>
					<div class="tg-weekpick">
						<button type="button" class="tg-step" data-nav="-1" data-busy-disable
							aria-label="<?php esc_attr_e( 'Previous week', 'ttcc-zmanim' ); ?>">&lsaquo;</button>
						<input type="date" data-role="start" data-busy-disable
							aria-labelledby="<?php echo esc_attr( $uid ); ?>-wk" />
						<button type="button" class="tg-step" data-nav="1" data-busy-disable
							aria-label="<?php esc_attr_e( 'Next week', 'ttcc-zmanim' ); ?>">&rsaquo;</button>
					</div>
					<button type="button" class="tg-link" data-role="today" data-busy-disable><?php esc_html_e( 'Jump to this week', 'ttcc-zmanim' ); ?></button>
				</div>

				<div class="tg-field">
					<span class="tg-label"><?php esc_html_e( 'Weeks on the sheet', 'ttcc-zmanim' ); ?></span>
					<div class="tg-seg tg-seg-weeks" role="group" aria-label="<?php esc_attr_e( 'Number of weeks', 'ttcc-zmanim' ); ?>">
						<?php for ( $i = 1; $i <= self::MAX_WEEKS; $i++ ) : ?>
							<button type="button" data-weeks="<?php echo esc_attr( $i ); ?>" data-busy-disable
								aria-pressed="<?php echo $i === $weeks ? 'true' : 'false'; ?>"><?php echo esc_html( $i ); ?></button>
						<?php endfor; ?>
					</div>
				</div>

				<div class="tg-field">
					<span class="tg-label"><?php esc_html_e( 'Pages', 'ttcc-zmanim' ); ?></span>
					<div class="tg-seg" role="group" aria-label="<?php esc_attr_e( 'Page layout', 'ttcc-zmanim' ); ?>">
						<button type="button" data-layout="" data-busy-disable aria-pressed="true"
							title="<?php esc_attr_e( 'The normal sheets: one week per page (or 4-up for a run of weeks).', 'ttcc-zmanim' ); ?>"><?php esc_html_e( 'Weekly', 'ttcc-zmanim' ); ?></button>
						<button type="button" data-layout="flow" data-busy-disable aria-pressed="false"
							title="<?php esc_attr_e( 'Everything on a single page in two columns — the Tishrei sheet. Classic style only.', 'ttcc-zmanim' ); ?>"><?php esc_html_e( 'One page', 'ttcc-zmanim' ); ?></button>
					</div>
				</div>
				<div class="tg-field">
					<span class="tg-label"><?php esc_html_e( 'Sheet style', 'ttcc-zmanim' ); ?></span>
					<div class="tg-seg" role="group" aria-label="<?php esc_attr_e( 'Sheet style', 'ttcc-zmanim' ); ?>">
						<?php foreach ( array( 'classic' => __( 'Classic', 'ttcc-zmanim' ), 'modern' => __( 'Modern', 'ttcc-zmanim' ) ) as $style => $label ) : ?>
							<button type="button" data-style="<?php echo esc_attr( $style ); ?>" data-busy-disable
								aria-pressed="<?php echo $style === $cfg['template'] ? 'true' : 'false'; ?>"><?php echo esc_html( $label ); ?></button>
						<?php endforeach; ?>
					</div>
				</div>
			</div>

			<div class="tg-actions">
				<button type="button" class="tg-primary" data-export="pdf" data-busy-disable><?php esc_html_e( 'Download PDF', 'ttcc-zmanim' ); ?></button>
				<button type="button" class="tg-wa-btn" data-export="png" data-variant="square" data-busy-disable
					title="<?php esc_attr_e( 'The sheet as printed, centred on a square 1:1 image (2160×2160) with a padded margin — the shape WhatsApp shows in full, in a chat or a status.', 'ttcc-zmanim' ); ?>"><?php esc_html_e( 'WhatsApp image', 'ttcc-zmanim' ); ?></button>
				<button type="button" class="tg-wa-btn" data-role="wa-show" data-busy-disable><?php esc_html_e( 'WhatsApp text', 'ttcc-zmanim' ); ?></button>
				<button type="button" data-export="png" data-variant="portrait" data-busy-disable
					title="<?php esc_attr_e( '3:4 portrait image (2160×2880) for a social post or a noticeboard screen.', 'ttcc-zmanim' ); ?>"><?php esc_html_e( 'Tall image', 'ttcc-zmanim' ); ?></button>
				<button type="button" data-role="edit-toggle" aria-expanded="false"><?php esc_html_e( 'Add or adjust times', 'ttcc-zmanim' ); ?></button>
				<span class="tg-spacer"></span>
				<span class="tg-status" data-role="status" role="status" aria-live="polite"></span>
			</div>

			<p class="tg-hint-line" data-role="pages-note" hidden></p>
			<p class="tg-alert" data-role="alert" role="alert" hidden></p>

			<aside class="tg-editor" data-role="editor" hidden>
				<div class="tg-editor-head">
					<h3 class="tg-editor-title"><?php esc_html_e( 'Times on this sheet', 'ttcc-zmanim' ); ?></h3>
					<button type="button" class="tg-mini is-danger" data-role="reset" hidden><?php esc_html_e( 'Undo all changes', 'ttcc-zmanim' ); ?></button>
				</div>
				<p class="tg-editor-hint"><?php esc_html_e( 'Change a minyan time, hide a line, or add your own. Astronomical times are calculated and cannot be edited. Changes apply to this sheet only — nothing is saved to the site.', 'ttcc-zmanim' ); ?></p>
				<div class="tg-editor-body" data-role="editor-body"></div>
			</aside>

			</div><!-- /.tg-side -->

			<div class="tg-preview-pane">
				<div class="tg-preview-bar">
					<span class="tg-seg tg-seg-view" role="group" aria-label="<?php esc_attr_e( 'What to preview', 'ttcc-zmanim' ); ?>">
						<?php // Default view: the tall 3:4 share image (see DEFAULT_VIEW in public/js/generator.js). ?>
						<button type="button" data-view="portrait" aria-pressed="true"
							title="<?php esc_attr_e( 'The tall 3:4 image, exactly as it will be sent', 'ttcc-zmanim' ); ?>"><?php esc_html_e( 'Tall 3:4', 'ttcc-zmanim' ); ?></button>
						<button type="button" data-view="square" aria-pressed="false"
							title="<?php esc_attr_e( 'The square 1:1 image, exactly as it will be sent', 'ttcc-zmanim' ); ?>"><?php esc_html_e( 'Square 1:1', 'ttcc-zmanim' ); ?></button>
						<button type="button" data-view="sheet" aria-pressed="false"
							title="<?php esc_attr_e( 'The printed A4 sheet, as the PDF download gives it', 'ttcc-zmanim' ); ?>"><?php esc_html_e( 'Sheet', 'ttcc-zmanim' ); ?></button>
					</span>
					<span class="tg-engine" data-role="engine"></span>
					<span class="tg-zoom">
						<button type="button" class="tg-step" data-zoom="-" aria-label="<?php esc_attr_e( 'Zoom out', 'ttcc-zmanim' ); ?>">&minus;</button>
						<span class="tg-zoom-val" data-role="zoom-val">100%</span>
						<button type="button" class="tg-step" data-zoom="+" aria-label="<?php esc_attr_e( 'Zoom in', 'ttcc-zmanim' ); ?>">+</button>
						<button type="button" class="tg-mini" data-zoom="fit"><?php esc_html_e( 'Fit', 'ttcc-zmanim' ); ?></button>
					</span>
				</div>
				<div class="tg-frame-scroll">
					<div class="tg-frame" data-role="frame">
						<iframe class="tg-preview" data-role="preview" title="<?php esc_attr_e( 'Timesheet preview', 'ttcc-zmanim' ); ?>"></iframe>
						<img class="tg-preview-img" data-role="image" alt="<?php esc_attr_e( 'The share image as it will be sent', 'ttcc-zmanim' ); ?>" hidden />
					</div>
				</div>
			</div>
		</div>

		<?php if ( $atts['footer'] ) : ?>
			<footer class="tg-foot"><?php echo esc_html( $atts['footer'] ); ?></footer>
		<?php endif; ?>
	</div>
</div>
<script type="application/json" class="ttcc-gen-config"><?php
	echo wp_json_encode( $cfg, JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_AMP ); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- JSON_HEX_TAG-encoded.
?></script>
		<?php
		return ob_get_clean();
	}

	/** Strings the front-end script needs (it renders the editor client-side). */
	private static function i18n() {
		return array(
			'week'                  => __( 'week', 'ttcc-zmanim' ),
			'weeks'                 => __( 'weeks', 'ttcc-zmanim' ),
			'working'               => __( 'Working…', 'ttcc-zmanim' ),
			'building'              => __( 'Building the sheet…', 'ttcc-zmanim' ),
			'buildingText'          => __( 'Building the message…', 'ttcc-zmanim' ),
			'buildingImage'         => __( 'Rendering the image…', 'ttcc-zmanim' ),
			'imageFailed'           => __( 'The image could not be rendered.', 'ttcc-zmanim' ),
			'preparing'             => __( 'Preparing your download…', 'ttcc-zmanim' ),
			'previewFailed'         => __( 'The sheet could not be built.', 'ttcc-zmanim' ),
			'textFailed'            => __( 'The message could not be built.', 'ttcc-zmanim' ),
			'throttled'             => __( 'Too many sheets in a short time — please wait a minute and try again.', 'ttcc-zmanim' ),
			'showEditor'            => __( 'Add or adjust times', 'ttcc-zmanim' ),
			'hideEditor'            => __( 'Hide the editor', 'ttcc-zmanim' ),
			/* translators: %d: how many printed sheets (pages) the range needs. */
			'squarePartial'         => __( 'This range fills %d sheets — the WhatsApp image shows the first one. The PDF has all of them.', 'ttcc-zmanim' ),
			'nothingToEdit'         => __( 'Nothing to edit for this range yet.', 'ttcc-zmanim' ),
			'notes'                 => __( 'Notes', 'ttcc-zmanim' ),
			'noteText'              => __( 'Note text', 'ttcc-zmanim' ),
			'addNote'               => __( '+ Add a note', 'ttcc-zmanim' ),
			'removeNote'            => __( 'Remove this note', 'ttcc-zmanim' ),
			'addLine'               => __( '+ Add a line', 'ttcc-zmanim' ),
			'add'                   => __( 'Add', 'ttcc-zmanim' ),
			'cancel'                => __( 'Cancel', 'ttcc-zmanim' ),
			'removeLine'            => __( 'Hide', 'ttcc-zmanim' ),
			'restoreLine'           => __( 'Restore', 'ttcc-zmanim' ),
			'hiddenLines'           => __( 'Hidden lines', 'ttcc-zmanim' ),
			'deleteLine'            => __( 'Delete', 'ttcc-zmanim' ),
			'revert'                => __( 'Revert', 'ttcc-zmanim' ),
			'revertHint'            => __( 'Back to the calculated time', 'ttcc-zmanim' ),
			'time'                  => __( 'Time', 'ttcc-zmanim' ),
			'noTime'                => __( ' No time', 'ttcc-zmanim' ),
			'section'               => __( 'Section', 'ttcc-zmanim' ),
			'newSection'            => __( '＋ New section…', 'ttcc-zmanim' ),
			'newSectionPlaceholder' => __( 'New section heading', 'ttcc-zmanim' ),
			'labelPlaceholder'      => __( 'Label — e.g. Special Mincha', 'ttcc-zmanim' ),
			'daysPlaceholder'       => __( 'Days (optional) — e.g. Wed.', 'ttcc-zmanim' ),
			'position'              => __( 'Where it goes', 'ttcc-zmanim' ),
			'atSectionEnd'          => __( 'At the end of the section', 'ttcc-zmanim' ),
			'after'                 => __( 'After:', 'ttcc-zmanim' ),
			'tagAdjusted'           => __( 'adjusted', 'ttcc-zmanim' ),
			'tagAdded'              => __( 'added', 'ttcc-zmanim' ),
			'tagZman'               => __( 'Calculated from the zmanim — not editable', 'ttcc-zmanim' ),
			'copied'                => __( 'Copied!', 'ttcc-zmanim' ),
			'confirmReset'          => __( 'Undo every change you made to this sheet?', 'ttcc-zmanim' ),
			/* translators: %1$s: zman name, %2$s: its time. */
			'earlierThan'           => __( 'earlier than %1$s (%2$s) — allowed, but please check.', 'ttcc-zmanim' ),
			/* translators: %1$s: zman name, %2$s: its time. */
			'laterThan'             => __( 'later than %1$s (%2$s) — allowed, but please check.', 'ttcc-zmanim' ),
		);
	}

	// --- REST callbacks -------------------------------------------------------

	public static function rest_preview( WP_REST_Request $req ) {
		$range = self::resolve_range( $req->get_param( 'start' ), $req->get_param( 'weeks' ) );
		if ( is_wp_error( $range ) ) {
			return $range;
		}
		$result = self::preview(
			$range,
			self::sanitize_template( $req->get_param( 'template' ) ),
			self::sanitize_overrides( $req->get_param( 'overrides' ) ),
			self::sanitize_layout( $req->get_param( 'layout' ) )
		);
		return is_wp_error( $result ) ? $result : rest_ensure_response( $result );
	}

	public static function rest_whatsapp( WP_REST_Request $req ) {
		$range = self::resolve_range( $req->get_param( 'start' ), $req->get_param( 'weeks' ) );
		if ( is_wp_error( $range ) ) {
			return $range;
		}
		$overrides = self::sanitize_overrides( $req->get_param( 'overrides' ) );
		$cache_key = self::cache_key( 'wa', $range, $overrides );
		if ( $cache_key ) {
			$hit = get_transient( $cache_key );
			if ( is_array( $hit ) ) {
				return rest_ensure_response( $hit );
			}
		}

		$throttled = self::throttle( 'build', self::THROTTLE_BUILD );
		if ( is_wp_error( $throttled ) ) {
			return $throttled;
		}
		$built = self::build_doc( $range, $overrides );
		if ( is_wp_error( $built ) ) {
			return self::as_error( $built );
		}
		$res = TTCC_Zmanim_Service_Client::whatsapp_text( $built['doc'] );
		if ( is_wp_error( $res ) ) {
			return self::as_error( $res );
		}
		$payload = array( 'text' => isset( $res['text'] ) ? (string) $res['text'] : '' );
		if ( $cache_key ) {
			set_transient( $cache_key, $payload, self::CACHE_TTL );
		}
		return rest_ensure_response( $payload );
	}

	/**
	 * Build + render for the preview pane. Returns {html, doc, engine_version}.
	 * Unedited sheets are served from (and stored in) a short-lived cache so
	 * browsing weeks costs the service nothing.
	 */
	private static function preview( $range, $template, $overrides, $layout = '' ) {
		$design = self::house_design( $template );
		// The design is part of the bucket, so editing the house style (or the
		// default preset) shows up on the next page load.
		$cache_key = self::cache_key( 'preview:' . $template . ':' . $layout . ':' . md5( (string) wp_json_encode( $design ) ), $range, $overrides );
		if ( $cache_key ) {
			$hit = get_transient( $cache_key );
			if ( is_array( $hit ) ) {
				return $hit;
			}
		}

		$throttled = self::throttle( 'build', self::THROTTLE_BUILD );
		if ( is_wp_error( $throttled ) ) {
			return $throttled;
		}
		$built = self::build_doc( $range, $overrides );
		if ( is_wp_error( $built ) ) {
			return self::as_error( $built );
		}
		$html = TTCC_Zmanim_Service_Client::render_html_doc( $built['doc'], 'print', $design, $layout );
		if ( is_wp_error( $html ) ) {
			return self::as_error( $html );
		}
		$payload = array(
			'html'           => $html['html'],
			'doc'            => $built['doc'],
			'engine_version' => $built['engine_version'],
		);
		if ( $cache_key ) {
			set_transient( $cache_key, $payload, self::CACHE_TTL );
		}
		return $payload;
	}

	// --- export ---------------------------------------------------------------

	/**
	 * admin-ajax (POST, front-end): stream a PDF/PNG of the visitor's sheet.
	 * POST fields: kind, variant (png only), start, weeks, template, overrides (JSON).
	 */
	public static function handle_export() {
		if ( ! self::can_use() ) {
			wp_die( esc_html__( 'The timesheet generator is not available.', 'ttcc-zmanim' ), '', array( 'response' => 403 ) );
		}
		// A signed-in visitor always has a fresh nonce, so verify theirs. Anonymous
		// visitors may hold a page-cached form, and this endpoint only re-renders
		// public timesheet data (no state change, nothing privileged), so a missing
		// nonce is not a security boundary there — the throttle bounds the cost.
		if ( is_user_logged_in() ) {
			$nonce = isset( $_POST['_wpnonce'] ) ? sanitize_text_field( wp_unslash( $_POST['_wpnonce'] ) ) : '';
			if ( ! wp_verify_nonce( $nonce, self::EXPORT_NONCE ) ) {
				wp_die( esc_html__( 'This page has expired — please reload it and try again.', 'ttcc-zmanim' ), '', array( 'response' => 403 ) );
			}
		}

		$kind = isset( $_POST['kind'] ) ? sanitize_key( wp_unslash( $_POST['kind'] ) ) : 'pdf';
		if ( ! in_array( $kind, array( 'pdf', 'png' ), true ) ) {
			wp_die( esc_html__( 'Unknown export type.', 'ttcc-zmanim' ), '', array( 'response' => 400 ) );
		}
		// Images come in two share shapes: 'square' (1:1, WhatsApp) and 'portrait'
		// (3:4, social). The PDF is always the print variant.
		$variant = 'print';
		if ( 'png' === $kind ) {
			$asked   = isset( $_POST['variant'] ) ? sanitize_key( wp_unslash( $_POST['variant'] ) ) : '';
			$variant = in_array( $asked, array( 'square', 'portrait' ), true ) ? $asked : 'square';
		}

		$range = self::resolve_range(
			isset( $_POST['start'] ) ? wp_unslash( $_POST['start'] ) : '', // phpcs:ignore WordPress.Security.ValidatedSanitizedInput -- validated in resolve_range().
			isset( $_POST['weeks'] ) ? wp_unslash( $_POST['weeks'] ) : 1  // phpcs:ignore WordPress.Security.ValidatedSanitizedInput -- cast to int in resolve_range().
		);
		if ( is_wp_error( $range ) ) {
			wp_die( esc_html( $range->get_error_message() ), '', array( 'response' => 400 ) );
		}

		$template  = self::sanitize_template( isset( $_POST['template'] ) ? wp_unslash( $_POST['template'] ) : '' ); // phpcs:ignore WordPress.Security.ValidatedSanitizedInput -- whitelisted in sanitize_template().
		$layout    = self::sanitize_layout( isset( $_POST['layout'] ) ? sanitize_key( wp_unslash( $_POST['layout'] ) ) : '' );
		$decoded   = isset( $_POST['overrides'] ) ? json_decode( wp_unslash( $_POST['overrides'] ), true ) : array(); // phpcs:ignore WordPress.Security.ValidatedSanitizedInput -- sanitized field-by-field below.
		$overrides = self::sanitize_overrides( $decoded );

		// An inline request is the page previewing the image rather than the
		// visitor saving it: same render, its own budget, and shown rather than
		// offered as a file.
		$inline    = ! empty( $_POST['inline'] );
		$throttled = $inline
			? self::throttle( 'view', self::THROTTLE_VIEW )
			: self::throttle( 'export', self::THROTTLE_EXPORT );
		if ( is_wp_error( $throttled ) ) {
			wp_die( esc_html( $throttled->get_error_message() ), '', array( 'response' => 429 ) );
		}

		$built = self::build_doc( $range, $overrides );
		if ( is_wp_error( $built ) ) {
			wp_die( esc_html( $built->get_error_message() ), '', array( 'response' => 503 ) );
		}
		$result = TTCC_Zmanim_Service_Client::render_binary( $kind, $built['doc'], $variant, self::house_design( $template ), $layout );
		if ( is_wp_error( $result ) ) {
			wp_die( esc_html( $result->get_error_message() ), '', array( 'response' => 503 ) );
		}

		$suffix   = ( 'png' === $kind ) ? '-' . $variant : '';
		$filename = 'ttcc-times-' . $range['start'] . $suffix . '.' . $kind;
		nocache_headers();
		header( 'Content-Type: ' . ( $result['content_type'] ? $result['content_type'] : 'application/octet-stream' ) );
		header( 'Content-Disposition: ' . ( $inline ? 'inline' : 'attachment' ) . '; filename="' . $filename . '"' );
		header( 'Content-Length: ' . strlen( $result['body'] ) );
		echo $result['body']; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- binary file body.
		exit;
	}

	// --- build ----------------------------------------------------------------

	/**
	 * Generate the doc for a range with the shul's saved edits applied underneath
	 * the visitor's own. Returns array{doc, engine_version} or WP_Error.
	 *
	 * Line overrides are keyed by rule_id, so one merged dict (visitor wins per
	 * key) is exact. Note edits are keyed by POSITION in the list the editor was
	 * shown, so they cannot be merged into one set — the visitor's indices refer
	 * to the already-shul-edited list. They are applied in order instead: the
	 * shul's inside build(), the visitor's on top of the result.
	 */
	private static function build_doc( $range, $overrides ) {
		$saved = self::saved_overrides( $range );
		$lines = $saved['lines'];
		foreach ( $overrides['lines'] as $key => $val ) {
			$lines[ $key ] = $val;
		}

		$built = TTCC_Zmanim_Sheet::build(
			$range['start'],
			$range['end'],
			array( 'lines' => $lines, 'notes' => $saved['notes'] )
		);
		if ( is_wp_error( $built ) ) {
			return $built;
		}
		if ( ! empty( $overrides['notes'] ) ) {
			$built['doc'] = TTCC_Zmanim_Sheet::apply_note_edits( $built['doc'], $overrides['notes'] );
		}
		return $built;
	}

	/**
	 * The line/note edits of every saved timesheet overlapping the range.
	 *
	 * Only block-scoped keys ("week:<sunday>|<rule_id>" / "day:<date>|…") are
	 * taken: a legacy bare key applies sheet-wide, which would leak one week's
	 * correction into the visitor's other weeks. Sheets come back oldest-edit
	 * first, so the most recently saved one wins a collision.
	 */
	private static function saved_overrides( $range ) {
		$lines = array();
		$notes = array();

		foreach ( TTCC_Zmanim_Storage::find_all_overlapping( $range['start'], $range['end'] ) as $sheet ) {
			$saved = is_array( $sheet['overrides'] ) ? $sheet['overrides'] : array();
			if ( isset( $saved['lines'] ) && is_array( $saved['lines'] ) ) {
				foreach ( $saved['lines'] as $key => $val ) {
					if ( self::is_scoped_line_key( (string) $key ) && is_array( $val ) ) {
						$lines[ (string) $key ] = $val;
					}
				}
			}
			if ( isset( $saved['notes'] ) && is_array( $saved['notes'] ) ) {
				foreach ( $saved['notes'] as $key => $val ) {
					if ( self::is_block_key( (string) $key ) && is_array( $val ) ) {
						$notes[ (string) $key ] = $val;
					}
				}
			}
		}

		return array( 'lines' => $lines, 'notes' => $notes );
	}

	/**
	 * The house design: the default style preset if one is set, else the Settings
	 * defaults. The visitor only chooses the template (classic/modern) — no
	 * design field ever comes from the request.
	 *
	 * Content sizing is always "fill", whatever the preset says. In "fixed" mode
	 * the sheet prints at its base font size and only shrinks, so a light week
	 * ends halfway down the page — dead paper on the PDF and a mostly-empty
	 * WhatsApp image. Filling scales the whole block uniformly, so the design's
	 * proportions are untouched; it just grows to the page. The dashboard keeps
	 * its Fixed option for an operator who wants it.
	 */
	private static function house_design( $template ) {
		$presets = TTCC_Zmanim_Storage::get_presets();
		$name    = $presets['default'];
		$design  = ( '' !== $name && isset( $presets['items'][ $name ]['design'] ) )
			? $presets['items'][ $name ]['design']
			: TTCC_Zmanim_Settings::design_defaults();

		$design = TTCC_Zmanim_Sheet::sanitize_design( is_array( $design ) ? $design : array() );
		$design['fit_mode'] = 'fill';

		return array( 'template' => $template ) + $design;
	}

	// --- request validation ---------------------------------------------------

	/**
	 * Snap $start to its Sunday, cap the span, and keep it inside the public
	 * window. Returns array{start, end} or WP_Error.
	 */
	private static function resolve_range( $start, $weeks ) {
		$start = trim( (string) $start );
		if ( ! preg_match( '/^\d{4}-\d{2}-\d{2}$/', $start ) ) {
			return new WP_Error( 'ttcc_bad_date', __( 'Pick a valid week.', 'ttcc-zmanim' ), array( 'status' => 400 ) );
		}
		$sunday = TTCC_Zmanim_Shabbos::sunday_of( $start );
		if ( ! $sunday || ! TTCC_Zmanim_Shabbos::in_window( $sunday ) ) {
			return new WP_Error( 'ttcc_out_of_range', __( 'That week is outside the range this page covers.', 'ttcc-zmanim' ), array( 'status' => 400 ) );
		}
		$weeks = (int) $weeks;
		$weeks = max( 1, min( self::MAX_WEEKS, $weeks ) );

		$end = date_create( $sunday );
		if ( ! $end ) {
			return new WP_Error( 'ttcc_bad_date', __( 'Pick a valid week.', 'ttcc-zmanim' ), array( 'status' => 400 ) );
		}
		$end->modify( '+' . ( $weeks * 7 - 1 ) . ' days' );

		return array( 'start' => $sunday, 'end' => $end->format( 'Y-m-d' ), 'weeks' => $weeks );
	}

	private static function sanitize_template( $template ) {
		return ( 'modern' === $template ) ? 'modern' : 'classic';
	}

	/** '' = normal weekly pages; 'flow' = everything on one page (Tishrei). */
	private static function sanitize_layout( $layout ) {
		return ( 'flow' === $layout ) ? 'flow' : '';
	}

	/**
	 * Whitelist a front-end override payload down to {lines, notes}: block-scoped
	 * keys, HH:MM times, plain-text labels, capped counts. Design keys, arbitrary
	 * line fields and unscoped (sheet-wide) keys are all dropped.
	 */
	public static function sanitize_overrides( $raw ) {
		$raw = is_array( $raw ) ? $raw : array();
		$out = array( 'lines' => array(), 'notes' => array() );

		$lines = ( isset( $raw['lines'] ) && is_array( $raw['lines'] ) ) ? $raw['lines'] : array();
		foreach ( $lines as $key => $val ) {
			if ( count( $out['lines'] ) >= self::MAX_LINE_EDITS ) {
				break;
			}
			$key = (string) $key;
			if ( ! self::is_scoped_line_key( $key ) || ! is_array( $val ) ) {
				continue;
			}
			$rule_id = substr( $key, strpos( $key, '|' ) + 1 );
			$line    = ( 0 === strpos( $rule_id, 'add:' ) )
				? self::sanitize_added_line( $val, $rule_id )
				: self::sanitize_line_edit( $val );
			if ( null !== $line ) {
				$out['lines'][ $key ] = $line;
			}
		}

		$notes = ( isset( $raw['notes'] ) && is_array( $raw['notes'] ) ) ? $raw['notes'] : array();
		foreach ( $notes as $key => $edit ) {
			if ( count( $out['notes'] ) >= self::MAX_NOTE_BLOCKS ) {
				break;
			}
			if ( ! self::is_block_key( (string) $key ) || ! is_array( $edit ) ) {
				continue;
			}
			$removed = array();
			$raw_rm  = ( isset( $edit['removed'] ) && is_array( $edit['removed'] ) ) ? $edit['removed'] : array();
			foreach ( $raw_rm as $index ) {
				$index = (int) $index;
				if ( $index >= 0 && $index < 200 && ! in_array( $index, $removed, true ) ) {
					$removed[] = $index;
				}
			}
			$added  = array();
			$raw_ad = ( isset( $edit['added'] ) && is_array( $edit['added'] ) ) ? $edit['added'] : array();
			foreach ( $raw_ad as $text ) {
				if ( count( $added ) >= self::MAX_ADDED_NOTES ) {
					break;
				}
				$text = self::plain_text( $text, 300 );
				if ( '' !== $text ) {
					$added[] = $text;
				}
			}
			if ( $removed || $added ) {
				$out['notes'][ (string) $key ] = array( 'removed' => $removed, 'added' => $added );
			}
		}

		return $out;
	}

	/** {"suppress":true} or {"time":"HH:MM"} — anything else is dropped. */
	private static function sanitize_line_edit( $val ) {
		if ( ! empty( $val['suppress'] ) ) {
			return array( 'suppress' => true );
		}
		$time = self::sanitize_time( isset( $val['time'] ) ? $val['time'] : '' );
		return ( '' === $time ) ? null : array( 'time' => $time );
	}

	/** A manually added line, rebuilt field by field (never passed through). */
	private static function sanitize_added_line( $val, $rule_id ) {
		$label = self::plain_text( isset( $val['label'] ) ? $val['label'] : '', 120 );
		if ( '' === $label ) {
			return null;
		}
		$kind = ( isset( $val['kind'] ) && 'freetext' === $val['kind'] ) ? 'freetext' : 'minyan';
		$time = self::sanitize_time( isset( $val['time'] ) ? $val['time'] : '' );
		if ( 'minyan' === $kind && '' === $time ) {
			return null; // a timed line without a valid time would print blank.
		}
		$section  = self::plain_text( isset( $val['section'] ) ? $val['section'] : '', 90 );
		$day_spec = self::plain_text( isset( $val['day_spec'] ) ? $val['day_spec'] : '', 40 );
		$date     = ( isset( $val['date'] ) && preg_match( '/^\d{4}-\d{2}-\d{2}$/', (string) $val['date'] ) ) ? (string) $val['date'] : null;

		$line = array(
			'rule_id'   => $rule_id,
			'section'   => ( '' !== $section ) ? $section : null,
			'label'     => $label,
			'kind'      => $kind,
			'day_spec'  => ( '' !== $day_spec ) ? $day_spec : null,
			'date'      => $date,
			'time'      => ( 'freetext' === $kind ) ? '' : $time,
			'qualifier' => null,
			'source'    => 'manual',
		);
		if ( isset( $val['after'] ) && preg_match( '/^[A-Za-z0-9_.:\-]{1,64}$/', (string) $val['after'] ) ) {
			$line['after'] = (string) $val['after'];
		}
		return $line;
	}

	private static function sanitize_time( $value ) {
		$value = trim( (string) $value );
		return preg_match( '/^(?:[01]\d|2[0-3]):[0-5]\d$/', $value ) ? $value : '';
	}

	/** Tag-stripped, single-line text, truncated without splitting a character. */
	private static function plain_text( $value, $max ) {
		$text = wp_strip_all_tags( (string) $value );
		// /u fails (returns null) on malformed UTF-8; fall back to a byte-wise
		// collapse so a mangled label degrades instead of becoming null.
		$flat = preg_replace( '/\s+/u', ' ', $text );
		if ( null === $flat ) {
			$flat = preg_replace( '/\s+/', ' ', $text );
		}
		$flat = trim( (string) $flat );
		return function_exists( 'mb_substr' ) ? mb_substr( $flat, 0, $max ) : substr( $flat, 0, $max );
	}

	/** "week:2026-08-02" / "day:2026-08-04". */
	private static function is_block_key( $key ) {
		return (bool) preg_match( '/^(?:week|day):\d{4}-\d{2}-\d{2}$/', $key );
	}

	/** A block key plus a rule id: "week:2026-08-02|weekday_mincha". */
	private static function is_scoped_line_key( $key ) {
		return (bool) preg_match( '/^(?:week|day):\d{4}-\d{2}-\d{2}\|[A-Za-z0-9_.:\-]{1,64}$/', $key );
	}

	// --- caching + throttling -------------------------------------------------

	/**
	 * Cache key for an UNEDITED sheet, or '' when the visitor has edits (those
	 * are one-off and never cached). Saved-sheet ids/timestamps are folded in, so
	 * an admin re-saving a week invalidates the front-end copy immediately.
	 */
	private static function cache_key( $bucket, $range, $overrides ) {
		if ( ! empty( $overrides['lines'] ) || ! empty( $overrides['notes'] ) ) {
			return '';
		}
		$stamp = array();
		foreach ( TTCC_Zmanim_Storage::find_all_overlapping( $range['start'], $range['end'] ) as $sheet ) {
			$stamp[] = $sheet['id'] . '@' . $sheet['updated_at'];
		}
		$set = TTCC_Zmanim_Storage::get_active_profile_set();
		if ( $set ) {
			$stamp[] = 'p' . $set['id'] . '@' . $set['updated_at'];
		}
		return 'ttcc_gen_' . md5( implode( '|', array(
			$bucket,
			$range['start'],
			$range['end'],
			TTCC_ZMANIM_VERSION,
			implode( ',', $stamp ),
		) ) );
	}

	/**
	 * Fixed-window per-IP throttle. Timesheet managers are exempt. Returns null
	 * when the request may proceed, or a 429 WP_Error.
	 */
	private static function throttle( $bucket, $limit ) {
		if ( current_user_can( TTCC_ZMANIM_CAP ) ) {
			return null;
		}
		$key   = 'ttcc_gen_rl_' . $bucket . '_' . md5( self::client_ip() . '|' . wp_salt() );
		$count = (int) get_transient( $key );
		if ( $count >= $limit ) {
			return new WP_Error(
				'ttcc_throttled',
				__( 'Too many timesheets in a short time. Please wait a minute and try again.', 'ttcc-zmanim' ),
				array( 'status' => 429 )
			);
		}
		set_transient( $key, $count + 1, self::THROTTLE_WINDOW );
		return null;
	}

	/** REMOTE_ADDR only — forwarded headers are visitor-controlled. */
	private static function client_ip() {
		$ip = isset( $_SERVER['REMOTE_ADDR'] ) ? (string) wp_unslash( $_SERVER['REMOTE_ADDR'] ) : '';
		return filter_var( $ip, FILTER_VALIDATE_IP ) ? $ip : 'unknown';
	}

	/** Turn a service failure into a 503 the front end can explain. */
	private static function as_error( WP_Error $err ) {
		$data   = $err->get_error_data();
		$status = ( is_array( $data ) && isset( $data['status'] ) && (int) $data['status'] >= 400 ) ? (int) $data['status'] : 503;
		return new WP_Error( 'ttcc_service', $err->get_error_message(), array( 'status' => $status ) );
	}
}
