<?php
/**
 * REST routes (namespace ttcc/v1) that the admin dashboard JS calls. JSON only;
 * binary exports stream via the admin-ajax handler in TTCC_Zmanim_Admin.
 *
 * Every route requires the timesheet capability. WordPress enforces the REST
 * nonce (X-WP-Nonce) for cookie-authenticated requests.
 *
 * @package TTCC_Zmanim
 */

defined( 'ABSPATH' ) || exit;

class TTCC_Zmanim_REST {

	const NS = 'ttcc/v1';

	public function register_routes() {
		$perm = array( $this, 'can_manage' );

		register_rest_route( self::NS, '/health', array(
			'methods'             => 'GET',
			'callback'            => array( $this, 'health' ),
			'permission_callback' => $perm,
		) );

		// Public (read-only, server-cached): the Shabbos & Yom Tov highlights
		// consumed by the [ttcc_shabbos] widget and the Shabbos signage screen.
		register_rest_route( self::NS, '/shabbos-times', array(
			'methods'             => 'GET',
			'callback'            => array( 'TTCC_Zmanim_Shabbos', 'rest_week' ),
			'permission_callback' => '__return_true',
			'args'                => array(
				'week' => array(
					'description' => __( 'Any date (YYYY-MM-DD) inside the wanted week; defaults to the current week.', 'ttcc-zmanim' ),
					'type'        => 'string',
					'required'    => false,
				),
			),
		) );

		register_rest_route( self::NS, '/preview', array(
			'methods'             => 'POST',
			'callback'            => array( $this, 'preview' ),
			'permission_callback' => $perm,
		) );

		register_rest_route( self::NS, '/whatsapp', array(
			'methods'             => 'POST',
			'callback'            => array( $this, 'whatsapp' ),
			'permission_callback' => $perm,
		) );

		register_rest_route( self::NS, '/timesheets', array(
			array(
				'methods'             => 'GET',
				'callback'            => array( $this, 'list_timesheets' ),
				'permission_callback' => $perm,
			),
			array(
				'methods'             => 'POST',
				'callback'            => array( $this, 'save_timesheet' ),
				'permission_callback' => $perm,
			),
		) );

		register_rest_route( self::NS, '/timesheets/(?P<id>\d+)', array(
			array(
				'methods'             => 'GET',
				'callback'            => array( $this, 'get_timesheet' ),
				'permission_callback' => $perm,
			),
			array(
				'methods'             => 'DELETE',
				'callback'            => array( $this, 'delete_timesheet' ),
				'permission_callback' => $perm,
			),
		) );

		register_rest_route( self::NS, '/profiles', array(
			array(
				'methods'             => 'GET',
				'callback'            => array( $this, 'get_profiles' ),
				'permission_callback' => $perm,
			),
			array(
				'methods'             => 'POST',
				'callback'            => array( $this, 'save_profiles' ),
				'permission_callback' => $perm,
			),
		) );

		register_rest_route( self::NS, '/profiles/reset', array(
			'methods'             => 'POST',
			'callback'            => array( $this, 'reset_profiles' ),
			'permission_callback' => $perm,
		) );

		register_rest_route( self::NS, '/presets', array(
			array(
				'methods'             => 'GET',
				'callback'            => array( $this, 'get_presets' ),
				'permission_callback' => $perm,
			),
			array(
				'methods'             => 'POST',
				'callback'            => array( $this, 'save_preset' ),
				'permission_callback' => $perm,
			),
		) );

		register_rest_route( self::NS, '/presets/delete', array(
			'methods'             => 'POST',
			'callback'            => array( $this, 'delete_preset' ),
			'permission_callback' => $perm,
		) );

		register_rest_route( self::NS, '/presets/default', array(
			'methods'             => 'POST',
			'callback'            => array( $this, 'set_default_preset' ),
			'permission_callback' => $perm,
		) );

		register_rest_route( self::NS, '/custom-fonts', array(
			array(
				'methods'             => 'GET',
				'callback'            => array( $this, 'get_custom_fonts' ),
				'permission_callback' => $perm,
			),
			array(
				'methods'             => 'POST',
				'callback'            => array( $this, 'save_custom_font' ),
				'permission_callback' => $perm,
			),
		) );

		register_rest_route( self::NS, '/custom-fonts/delete', array(
			'methods'             => 'POST',
			'callback'            => array( $this, 'delete_custom_font' ),
			'permission_callback' => $perm,
		) );
	}

	public function can_manage() {
		return current_user_can( TTCC_ZMANIM_CAP );
	}

	// --- callbacks ----------------------------------------------------------

	public function health() {
		return rest_ensure_response( TTCC_Zmanim_Service_Client::health() );
	}

	/**
	 * Build + render a preview for a range and (optional) live overrides.
	 * Returns {html, doc, engine_version}. 503 if the service is unreachable.
	 */
	public function preview( WP_REST_Request $req ) {
		$start     = $this->req_date( $req, 'start' );
		$end       = $this->req_date( $req, 'end' );
		$overrides = $req->get_param( 'overrides' );
		if ( ! $start || ! $end ) {
			return new WP_Error( 'ttcc_bad_request', __( 'start and end (YYYY-MM-DD) are required.', 'ttcc-zmanim' ), array( 'status' => 400 ) );
		}
		$overrides = is_array( $overrides ) ? $overrides : array();

		$built = TTCC_Zmanim_Sheet::build( $start, $end, $overrides );
		if ( is_wp_error( $built ) ) {
			return $this->service_error( $built );
		}
		$variant = 'portrait' === $req->get_param( 'variant' ) ? 'portrait' : 'print';
		$design  = TTCC_Zmanim_Sheet::design_from_overrides( $overrides );
		$html    = TTCC_Zmanim_Service_Client::render_html_doc( $built['doc'], $variant, $design );
		if ( is_wp_error( $html ) ) {
			return $this->service_error( $html );
		}
		return rest_ensure_response( array(
			'html'           => $html['html'],
			'doc'            => $built['doc'],
			'engine_version' => $built['engine_version'],
		) );
	}

	/**
	 * Build a doc for the range + overrides and render the WhatsApp broadcast.
	 * Returns {text}. 503 if the service is unreachable.
	 */
	public function whatsapp( WP_REST_Request $req ) {
		$start = $this->req_date( $req, 'start' );
		$end   = $this->req_date( $req, 'end' );
		if ( ! $start || ! $end ) {
			return new WP_Error( 'ttcc_bad_request', __( 'start and end (YYYY-MM-DD) are required.', 'ttcc-zmanim' ), array( 'status' => 400 ) );
		}
		$overrides = $req->get_param( 'overrides' );
		$overrides = is_array( $overrides ) ? $overrides : array();

		$built = TTCC_Zmanim_Sheet::build( $start, $end, $overrides );
		if ( is_wp_error( $built ) ) {
			return $this->service_error( $built );
		}
		$res = TTCC_Zmanim_Service_Client::whatsapp_text( $built['doc'] );
		if ( is_wp_error( $res ) ) {
			return $this->service_error( $res );
		}
		return rest_ensure_response( array( 'text' => isset( $res['text'] ) ? $res['text'] : '' ) );
	}

	public function list_timesheets() {
		return rest_ensure_response( TTCC_Zmanim_Storage::list_timesheets() );
	}

	public function get_timesheet( WP_REST_Request $req ) {
		$sheet = TTCC_Zmanim_Storage::get_timesheet( (int) $req['id'] );
		if ( ! $sheet ) {
			return new WP_Error( 'ttcc_not_found', __( 'Timesheet not found.', 'ttcc-zmanim' ), array( 'status' => 404 ) );
		}
		return rest_ensure_response( $sheet );
	}

	public function save_timesheet( WP_REST_Request $req ) {
		$start = $this->req_date( $req, 'start' );
		$end   = $this->req_date( $req, 'end' );
		if ( ! $start || ! $end ) {
			return new WP_Error( 'ttcc_bad_request', __( 'start and end are required.', 'ttcc-zmanim' ), array( 'status' => 400 ) );
		}
		$overrides = $req->get_param( 'overrides' );
		$overrides = is_array( $overrides ) ? $overrides : array();

		// Re-generate the snapshot server-side so the stored blocks reflect the
		// authoritative engine output for the saved overrides.
		$built = TTCC_Zmanim_Sheet::build( $start, $end, $overrides );
		if ( is_wp_error( $built ) ) {
			return $this->service_error( $built );
		}
		$set = TTCC_Zmanim_Storage::get_active_profile_set();

		$id = TTCC_Zmanim_Storage::save_timesheet( array(
			'id'             => (int) $req->get_param( 'id' ),
			'title'          => sanitize_text_field( (string) $req->get_param( 'title' ) ),
			'format'         => isset( $built['doc']['format'] ) ? $built['doc']['format'] : 'weekly',
			'start_date'     => $start,
			'end_date'       => $end,
			'status'         => in_array( $req->get_param( 'status' ), array( 'draft', 'final' ), true ) ? $req->get_param( 'status' ) : 'draft',
			'blocks'         => $built['doc'],
			'overrides'      => $overrides,
			'engine_version' => $built['engine_version'],
			'profile_set_id' => $set ? (int) $set['id'] : null,
		) );

		return rest_ensure_response( TTCC_Zmanim_Storage::get_timesheet( $id ) );
	}

	public function delete_timesheet( WP_REST_Request $req ) {
		$ok = TTCC_Zmanim_Storage::delete_timesheet( (int) $req['id'] );
		return rest_ensure_response( array( 'deleted' => $ok ) );
	}

	public function get_profiles() {
		$set = TTCC_Zmanim_Storage::get_active_profile_set();
		if ( ! $set ) {
			// Seed lazily from the service defaults on first read.
			return $this->reset_profiles();
		}
		return rest_ensure_response( array( 'profiles' => $set['profiles'], 'notes' => $set['notes'] ) );
	}

	public function save_profiles( WP_REST_Request $req ) {
		$profiles = $req->get_param( 'profiles' );
		$notes    = $req->get_param( 'notes' );
		if ( ! is_array( $profiles ) ) {
			return new WP_Error( 'ttcc_bad_request', __( 'profiles must be an array.', 'ttcc-zmanim' ), array( 'status' => 400 ) );
		}
		TTCC_Zmanim_Storage::save_active_profile_set( $profiles, is_array( $notes ) ? $notes : array() );
		$set = TTCC_Zmanim_Storage::get_active_profile_set();
		return rest_ensure_response( array( 'profiles' => $set['profiles'], 'notes' => $set['notes'] ) );
	}

	public function reset_profiles() {
		$defaults = TTCC_Zmanim_Service_Client::default_profiles();
		if ( is_wp_error( $defaults ) ) {
			return $this->service_error( $defaults );
		}
		$profiles = isset( $defaults['profiles'] ) ? $defaults['profiles'] : array();
		$notes    = isset( $defaults['notes'] ) ? $defaults['notes'] : array();
		TTCC_Zmanim_Storage::save_active_profile_set( $profiles, $notes, 'Active schedule (from engine defaults)' );
		return rest_ensure_response( array( 'profiles' => $profiles, 'notes' => $notes ) );
	}

	// --- style presets ------------------------------------------------------

	public function get_presets() {
		return rest_ensure_response( TTCC_Zmanim_Storage::get_presets() );
	}

	public function save_preset( WP_REST_Request $req ) {
		$name = (string) $req->get_param( 'name' );
		if ( '' === trim( $name ) ) {
			return new WP_Error( 'ttcc_bad_request', __( 'A preset name is required.', 'ttcc-zmanim' ), array( 'status' => 400 ) );
		}
		TTCC_Zmanim_Storage::save_preset( $name, (string) $req->get_param( 'template' ), $req->get_param( 'design' ) );
		return rest_ensure_response( TTCC_Zmanim_Storage::get_presets() );
	}

	public function delete_preset( WP_REST_Request $req ) {
		TTCC_Zmanim_Storage::delete_preset( (string) $req->get_param( 'name' ) );
		return rest_ensure_response( TTCC_Zmanim_Storage::get_presets() );
	}

	public function set_default_preset( WP_REST_Request $req ) {
		TTCC_Zmanim_Storage::set_default_preset( (string) $req->get_param( 'name' ) );
		return rest_ensure_response( TTCC_Zmanim_Storage::get_presets() );
	}

	// --- saved custom fonts --------------------------------------------------

	public function get_custom_fonts() {
		return rest_ensure_response( TTCC_Zmanim_Storage::get_custom_fonts() );
	}

	public function save_custom_font( WP_REST_Request $req ) {
		$name = (string) $req->get_param( 'name' );
		if ( '' === trim( $name ) ) {
			return new WP_Error( 'ttcc_bad_request', __( 'A font name is required.', 'ttcc-zmanim' ), array( 'status' => 400 ) );
		}
		TTCC_Zmanim_Storage::save_custom_font( $name, (string) $req->get_param( 'family' ), (string) $req->get_param( 'source' ) );
		return rest_ensure_response( TTCC_Zmanim_Storage::get_custom_fonts() );
	}

	public function delete_custom_font( WP_REST_Request $req ) {
		TTCC_Zmanim_Storage::delete_custom_font( (string) $req->get_param( 'name' ) );
		return rest_ensure_response( TTCC_Zmanim_Storage::get_custom_fonts() );
	}

	// --- helpers ------------------------------------------------------------

	private function req_date( WP_REST_Request $req, $key ) {
		$val = (string) $req->get_param( $key );
		return preg_match( '/^\d{4}-\d{2}-\d{2}$/', $val ) ? $val : '';
	}

	/**
	 * Turn a service WP_Error into a 503 so the dashboard can show degraded mode.
	 */
	private function service_error( WP_Error $err ) {
		$data   = $err->get_error_data();
		$status = ( is_array( $data ) && isset( $data['status'] ) && (int) $data['status'] >= 400 ) ? (int) $data['status'] : 503;
		return new WP_Error( 'ttcc_service', $err->get_error_message(), array( 'status' => $status ) );
	}
}
