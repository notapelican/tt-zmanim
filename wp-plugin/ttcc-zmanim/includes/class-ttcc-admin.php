<?php
/**
 * Admin surface: menu pages, asset enqueue, and the streaming export handler.
 *
 * @package TTCC_Zmanim
 */

defined( 'ABSPATH' ) || exit;

class TTCC_Zmanim_Admin {

	const MENU = 'ttcc-zmanim';

	public function hooks() {
		add_action( 'admin_menu', array( $this, 'menu' ) );
		add_action( 'admin_enqueue_scripts', array( $this, 'enqueue' ) );
		add_action( 'wp_ajax_ttcc_export', array( $this, 'export' ) );
	}

	public function menu() {
		add_menu_page(
			__( 'TTCC Timesheets', 'ttcc-zmanim' ),
			__( 'Timesheets', 'ttcc-zmanim' ),
			TTCC_ZMANIM_CAP,
			self::MENU,
			array( $this, 'render_dashboard' ),
			'dashicons-calendar-alt',
			26
		);
		add_submenu_page( self::MENU, __( 'Dashboard', 'ttcc-zmanim' ), __( 'Dashboard', 'ttcc-zmanim' ), TTCC_ZMANIM_CAP, self::MENU, array( $this, 'render_dashboard' ) );
		add_submenu_page( self::MENU, __( 'Archive', 'ttcc-zmanim' ), __( 'Archive', 'ttcc-zmanim' ), TTCC_ZMANIM_CAP, self::MENU . '-archive', array( $this, 'render_archive' ) );
		add_submenu_page( self::MENU, __( 'Schedule profiles', 'ttcc-zmanim' ), __( 'Schedule profiles', 'ttcc-zmanim' ), TTCC_ZMANIM_CAP, self::MENU . '-profiles', array( $this, 'render_profiles' ) );
		add_submenu_page( self::MENU, __( 'Settings', 'ttcc-zmanim' ), __( 'Settings', 'ttcc-zmanim' ), TTCC_ZMANIM_CAP, self::MENU . '-settings', array( 'TTCC_Zmanim_Settings', 'render_page' ) );
	}

	public function enqueue( $hook ) {
		if ( false === strpos( (string) $hook, self::MENU ) ) {
			return;
		}
		wp_enqueue_style( 'ttcc-admin', TTCC_ZMANIM_URL . 'admin/css/admin.css', array(), TTCC_ZMANIM_VERSION );

		$common = array(
			'restUrl'   => esc_url_raw( rest_url( TTCC_Zmanim_REST::NS ) ),
			'nonce'     => wp_create_nonce( 'wp_rest' ),
			'ajaxUrl'   => admin_url( 'admin-ajax.php' ),
			'exportNonce' => wp_create_nonce( 'ttcc_export' ),
			'i18n'      => array(
				'offline' => __( 'Sheet service is offline — generating, preview and export are unavailable. Edits you make are kept and will save; the preview will refresh when the service returns.', 'ttcc-zmanim' ),
			),
		);

		wp_register_script( 'ttcc-dashboard', TTCC_ZMANIM_URL . 'admin/js/dashboard.js', array(), TTCC_ZMANIM_VERSION, true );
		wp_register_script( 'ttcc-profiles', TTCC_ZMANIM_URL . 'admin/js/profiles.js', array(), TTCC_ZMANIM_VERSION, true );

		if ( strpos( $hook, self::MENU . '-profiles' ) !== false ) {
			wp_enqueue_script( 'ttcc-profiles' );
			wp_localize_script( 'ttcc-profiles', 'TTCC', $common );
		} elseif ( strpos( $hook, self::MENU . '-archive' ) !== false || strpos( $hook, self::MENU . '-settings' ) !== false ) {
			// Archive/settings render server-side; no editor JS needed.
			return;
		} else {
			wp_enqueue_media(); // logo picker in the Design panel
			wp_enqueue_script( 'ttcc-dashboard' );
			$common['designDefaults'] = TTCC_Zmanim_Settings::design_defaults();
			wp_localize_script( 'ttcc-dashboard', 'TTCC', $common );
		}
	}

	public function render_dashboard() {
		if ( ! current_user_can( TTCC_ZMANIM_CAP ) ) {
			wp_die( esc_html__( 'Permission denied.', 'ttcc-zmanim' ) );
		}
		$edit_id = isset( $_GET['sheet'] ) ? (int) $_GET['sheet'] : 0; // phpcs:ignore WordPress.Security.NonceVerification.Recommended
		include TTCC_ZMANIM_DIR . 'admin/views/dashboard.php';
	}

	public function render_archive() {
		if ( ! current_user_can( TTCC_ZMANIM_CAP ) ) {
			wp_die( esc_html__( 'Permission denied.', 'ttcc-zmanim' ) );
		}
		$sheets = TTCC_Zmanim_Storage::list_timesheets();
		include TTCC_ZMANIM_DIR . 'admin/views/archive.php';
	}

	public function render_profiles() {
		if ( ! current_user_can( TTCC_ZMANIM_CAP ) ) {
			wp_die( esc_html__( 'Permission denied.', 'ttcc-zmanim' ) );
		}
		include TTCC_ZMANIM_DIR . 'admin/views/profiles.php';
	}

	/**
	 * admin-ajax: stream a PDF/PNG/DOCX export. GET params: kind, variant, and
	 * either sheet (stored id) or start/end/overrides (ad-hoc). Nonce + cap checked.
	 */
	public function export() {
		if ( ! current_user_can( TTCC_ZMANIM_CAP ) ) {
			wp_die( esc_html__( 'Permission denied.', 'ttcc-zmanim' ), '', array( 'response' => 403 ) );
		}
		check_admin_referer( 'ttcc_export' );

		$kind = isset( $_GET['kind'] ) ? sanitize_key( wp_unslash( $_GET['kind'] ) ) : 'pdf';
		if ( ! in_array( $kind, array( 'pdf', 'png', 'docx' ), true ) ) {
			wp_die( esc_html__( 'Unknown export type.', 'ttcc-zmanim' ) );
		}
		$variant = ( isset( $_GET['variant'] ) && 'portrait' === $_GET['variant'] ) ? 'portrait' : 'print';

		$sheet_id = isset( $_GET['sheet'] ) ? (int) $_GET['sheet'] : 0;
		if ( $sheet_id ) {
			$sheet = TTCC_Zmanim_Storage::get_timesheet( $sheet_id );
			if ( ! $sheet ) {
				wp_die( esc_html__( 'Timesheet not found.', 'ttcc-zmanim' ) );
			}
			$doc      = $sheet['blocks'];
			$design   = TTCC_Zmanim_Sheet::design_from_overrides( isset( $sheet['overrides'] ) ? $sheet['overrides'] : array() );
			$basename = 'ttcc-' . $sheet['start_date'];
		} else {
			$start = isset( $_GET['start'] ) ? sanitize_text_field( wp_unslash( $_GET['start'] ) ) : '';
			$end   = isset( $_GET['end'] ) ? sanitize_text_field( wp_unslash( $_GET['end'] ) ) : '';
			if ( ! preg_match( '/^\d{4}-\d{2}-\d{2}$/', $start ) || ! preg_match( '/^\d{4}-\d{2}-\d{2}$/', $end ) ) {
				wp_die( esc_html__( 'Invalid date range.', 'ttcc-zmanim' ) );
			}
			$overrides = array();
			if ( isset( $_GET['overrides'] ) ) {
				$decoded   = json_decode( wp_unslash( $_GET['overrides'] ), true ); // phpcs:ignore WordPress.Security.ValidatedSanitizedInput
				$overrides = is_array( $decoded ) ? $decoded : array();
			}
			$built = TTCC_Zmanim_Sheet::build( $start, $end, $overrides );
			if ( is_wp_error( $built ) ) {
				wp_die( esc_html( $built->get_error_message() ) );
			}
			$doc      = $built['doc'];
			$design   = TTCC_Zmanim_Sheet::design_from_overrides( $overrides );
			$basename = 'ttcc-' . $start;
		}

		$result = TTCC_Zmanim_Service_Client::render_binary( $kind, $doc, $variant, $design );
		if ( is_wp_error( $result ) ) {
			wp_die( esc_html( $result->get_error_message() ) );
		}

		if ( $sheet_id ) {
			TTCC_Zmanim_Storage::append_export_history( $sheet_id, array(
				'kind'    => $kind,
				'variant' => $variant,
				'at'      => current_time( 'mysql' ),
				'by'      => get_current_user_id(),
			) );
		}

		$ext  = ( 'docx' === $kind ) ? 'docx' : $kind;
		$type = $result['content_type'] ? $result['content_type'] : 'application/octet-stream';

		nocache_headers();
		header( 'Content-Type: ' . $type );
		header( 'Content-Disposition: attachment; filename="' . $basename . '.' . $ext . '"' );
		header( 'Content-Length: ' . strlen( $result['body'] ) );
		echo $result['body']; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- binary file body.
		exit;
	}
}
