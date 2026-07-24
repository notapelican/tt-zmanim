<?php
/**
 * Plugin bootstrap: wires activation, capabilities, admin, public surfaces and
 * REST routes. Kept thin — each concern lives in its own class.
 *
 * @package TTCC_Zmanim
 */

defined( 'ABSPATH' ) || exit;

class TTCC_Zmanim_Plugin {

	private static $instance = null;

	public static function instance() {
		if ( null === self::$instance ) {
			self::$instance = new self();
		}
		return self::$instance;
	}

	private function __construct() {
		add_action( 'admin_init', array( 'TTCC_Zmanim_Settings', 'register' ) );

		$admin = new TTCC_Zmanim_Admin();
		$admin->hooks();

		$public = new TTCC_Zmanim_Public();
		$public->hooks();

		$rest = new TTCC_Zmanim_REST();
		add_action( 'rest_api_init', array( $rest, 'register_routes' ) );

		// Flush rewrites once per plugin version so rules added in an update
		// (e.g. the /shabbos signage variant) work without a re-activation.
		add_action( 'init', array( __CLASS__, 'maybe_flush_rewrites' ), 20 );
	}

	public static function maybe_flush_rewrites() {
		if ( get_option( 'ttcc_zmanim_rewrites' ) !== TTCC_ZMANIM_VERSION ) {
			flush_rewrite_rules();
			update_option( 'ttcc_zmanim_rewrites', TTCC_ZMANIM_VERSION, false );
		}
	}

	public static function activate() {
		TTCC_Zmanim_Storage::install();

		// Grant the timesheet capability to administrators.
		$role = get_role( 'administrator' );
		if ( $role && ! $role->has_cap( TTCC_ZMANIM_CAP ) ) {
			$role->add_cap( TTCC_ZMANIM_CAP );
		}

		// Ensure a piSignage slug exists.
		$opts = get_option( TTCC_Zmanim_Settings::OPTION, array() );
		if ( empty( $opts['pisignage_slug'] ) ) {
			$opts['pisignage_slug'] = wp_generate_password( 20, false, false );
			update_option( TTCC_Zmanim_Settings::OPTION, $opts );
		}

		// Register rewrite for the signage page, then flush.
		TTCC_Zmanim_Public::add_rewrite_rules();
		flush_rewrite_rules();
	}

	public static function deactivate() {
		flush_rewrite_rules();
	}
}
