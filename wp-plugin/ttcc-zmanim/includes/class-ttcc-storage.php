<?php
/**
 * Persistence layer: custom tables for timesheets and profile sets.
 *
 * All sheet/override/profile state lives here in WordPress (SiteGround MySQL);
 * the Python sheet service is stateless. Mirrors the `Timesheet` model in
 * engine/rules.py (blocks + overrides + export_history) plus an engine_version
 * stamp so "reprint the stored snapshot" is distinguishable from "regenerate".
 *
 * @package TTCC_Zmanim
 */

defined( 'ABSPATH' ) || exit;

class TTCC_Zmanim_Storage {

	public static function timesheets_table() {
		global $wpdb;
		return $wpdb->prefix . 'ttcc_timesheets';
	}

	public static function profile_sets_table() {
		global $wpdb;
		return $wpdb->prefix . 'ttcc_profile_sets';
	}

	/**
	 * Create/upgrade tables. Called on activation via dbDelta.
	 */
	public static function install() {
		global $wpdb;
		require_once ABSPATH . 'wp-admin/includes/upgrade.php';
		$charset = $wpdb->get_charset_collate();
		$sheets  = self::timesheets_table();
		$psets   = self::profile_sets_table();

		dbDelta(
			"CREATE TABLE {$sheets} (
				id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
				title VARCHAR(255) NOT NULL DEFAULT '',
				format VARCHAR(32) NOT NULL DEFAULT 'weekly',
				start_date DATE NOT NULL,
				end_date DATE NOT NULL,
				status VARCHAR(20) NOT NULL DEFAULT 'draft',
				blocks LONGTEXT NULL,
				overrides LONGTEXT NULL,
				engine_version VARCHAR(64) NOT NULL DEFAULT '',
				profile_set_id BIGINT UNSIGNED NULL,
				export_history LONGTEXT NULL,
				created_at DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00',
				updated_at DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00',
				PRIMARY KEY  (id),
				KEY start_date (start_date),
				KEY status (status)
			) {$charset};"
		);

		dbDelta(
			"CREATE TABLE {$psets} (
				id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
				name VARCHAR(255) NOT NULL DEFAULT '',
				profiles LONGTEXT NULL,
				notes LONGTEXT NULL,
				is_active TINYINT(1) NOT NULL DEFAULT 0,
				updated_at DATETIME NOT NULL DEFAULT '1970-01-01 00:00:00',
				PRIMARY KEY  (id),
				KEY is_active (is_active)
			) {$charset};"
		);
	}

	// --- timesheets ---------------------------------------------------------

	public static function get_timesheet( $id ) {
		global $wpdb;
		$row = $wpdb->get_row(
			$wpdb->prepare( 'SELECT * FROM ' . self::timesheets_table() . ' WHERE id = %d', $id ),
			ARRAY_A
		);
		return $row ? self::decode_timesheet( $row ) : null;
	}

	public static function list_timesheets( $limit = 100, $offset = 0 ) {
		global $wpdb;
		$rows = $wpdb->get_results(
			$wpdb->prepare(
				'SELECT id, title, format, start_date, end_date, status, engine_version, updated_at
				 FROM ' . self::timesheets_table() . ' ORDER BY start_date DESC, id DESC LIMIT %d OFFSET %d',
				$limit,
				$offset
			),
			ARRAY_A
		);
		return $rows ?: array();
	}

	/**
	 * Insert or update a timesheet. $data uses PHP-native values; JSON columns
	 * are encoded here. Returns the row id.
	 */
	public static function save_timesheet( $data ) {
		global $wpdb;
		$now  = current_time( 'mysql' );
		$cols = array(
			'title'          => isset( $data['title'] ) ? (string) $data['title'] : '',
			'format'         => isset( $data['format'] ) ? (string) $data['format'] : 'weekly',
			'start_date'     => (string) $data['start_date'],
			'end_date'       => (string) $data['end_date'],
			'status'         => isset( $data['status'] ) ? (string) $data['status'] : 'draft',
			'blocks'         => wp_json_encode( isset( $data['blocks'] ) ? $data['blocks'] : array() ),
			'overrides'      => wp_json_encode( isset( $data['overrides'] ) ? $data['overrides'] : (object) array() ),
			'engine_version' => isset( $data['engine_version'] ) ? (string) $data['engine_version'] : '',
			'profile_set_id' => isset( $data['profile_set_id'] ) ? (int) $data['profile_set_id'] : null,
			'export_history' => wp_json_encode( isset( $data['export_history'] ) ? $data['export_history'] : array() ),
			'updated_at'     => $now,
		);

		if ( ! empty( $data['id'] ) ) {
			$wpdb->update( self::timesheets_table(), $cols, array( 'id' => (int) $data['id'] ) );
			return (int) $data['id'];
		}
		$cols['created_at'] = $now;
		$wpdb->insert( self::timesheets_table(), $cols );
		return (int) $wpdb->insert_id;
	}

	public static function delete_timesheet( $id ) {
		global $wpdb;
		return (bool) $wpdb->delete( self::timesheets_table(), array( 'id' => (int) $id ) );
	}

	public static function append_export_history( $id, $entry ) {
		$sheet = self::get_timesheet( $id );
		if ( ! $sheet ) {
			return false;
		}
		$history   = isset( $sheet['export_history'] ) && is_array( $sheet['export_history'] ) ? $sheet['export_history'] : array();
		$history[] = $entry;
		global $wpdb;
		$wpdb->update(
			self::timesheets_table(),
			array( 'export_history' => wp_json_encode( $history ), 'updated_at' => current_time( 'mysql' ) ),
			array( 'id' => (int) $id )
		);
		return true;
	}

	private static function decode_timesheet( $row ) {
		$row['blocks']         = self::decode_json( $row['blocks'], array() );
		$row['overrides']      = self::decode_json( $row['overrides'], array() );
		$row['export_history'] = self::decode_json( $row['export_history'], array() );
		return $row;
	}

	// --- profile sets -------------------------------------------------------

	public static function get_active_profile_set() {
		global $wpdb;
		$row = $wpdb->get_row(
			'SELECT * FROM ' . self::profile_sets_table() . ' WHERE is_active = 1 ORDER BY id DESC LIMIT 1',
			ARRAY_A
		);
		if ( ! $row ) {
			return null;
		}
		$row['profiles'] = self::decode_json( $row['profiles'], array() );
		$row['notes']    = self::decode_json( $row['notes'], array() );
		return $row;
	}

	/**
	 * Store the active profile set (single active set in v1). Deactivates others.
	 */
	public static function save_active_profile_set( $profiles, $notes, $name = 'Active schedule' ) {
		global $wpdb;
		$existing = self::get_active_profile_set();
		$cols     = array(
			'name'       => (string) $name,
			'profiles'   => wp_json_encode( $profiles ),
			'notes'      => wp_json_encode( $notes ),
			'is_active'  => 1,
			'updated_at' => current_time( 'mysql' ),
		);
		if ( $existing ) {
			$wpdb->update( self::profile_sets_table(), $cols, array( 'id' => (int) $existing['id'] ) );
			return (int) $existing['id'];
		}
		$wpdb->insert( self::profile_sets_table(), $cols );
		return (int) $wpdb->insert_id;
	}

	// --- style presets ------------------------------------------------------
	// Named design presets (fonts, sizes, logo, colors, layout) stored site-wide
	// as one option: { default: <name|''>, items: { <name>: {template, design} } }.

	const PRESETS_OPTION = 'ttcc_zmanim_presets';

	public static function get_presets() {
		$opt = get_option( self::PRESETS_OPTION, array() );
		if ( ! is_array( $opt ) ) {
			$opt = array();
		}
		return array(
			'default' => isset( $opt['default'] ) ? (string) $opt['default'] : '',
			'items'   => ( isset( $opt['items'] ) && is_array( $opt['items'] ) ) ? $opt['items'] : array(),
		);
	}

	/** Upsert a preset by name. $design is sanitized to the whitelisted shape. */
	public static function save_preset( $name, $template, $design ) {
		$name = trim( sanitize_text_field( (string) $name ) );
		if ( '' === $name ) {
			return false;
		}
		$opt = self::get_presets();
		$opt['items'][ $name ] = array(
			'template' => ( 'modern' === $template ) ? 'modern' : 'classic',
			'design'   => TTCC_Zmanim_Sheet::sanitize_design( is_array( $design ) ? $design : array() ),
		);
		update_option( self::PRESETS_OPTION, $opt, false );
		return true;
	}

	public static function delete_preset( $name ) {
		$name = (string) $name;
		$opt  = self::get_presets();
		unset( $opt['items'][ $name ] );
		if ( $opt['default'] === $name ) {
			$opt['default'] = '';
		}
		update_option( self::PRESETS_OPTION, $opt, false );
		return true;
	}

	/** Set (or clear, with '') the preset new sheets inherit. */
	public static function set_default_preset( $name ) {
		$name = (string) $name;
		$opt  = self::get_presets();
		$opt['default'] = ( '' === $name || isset( $opt['items'][ $name ] ) ) ? $name : $opt['default'];
		update_option( self::PRESETS_OPTION, $opt, false );
		return true;
	}

	// --- saved custom fonts --------------------------------------------------
	// A small site-wide library of named custom font families (a Google Fonts
	// name or an Adobe Fonts/Typekit kebab-case slug) so a family typed once
	// can be picked again like a built-in font instead of retyped every time.
	// Stored as: { items: { <name>: { family, source } } }.

	const CUSTOM_FONTS_OPTION = 'ttcc_zmanim_custom_fonts';

	public static function get_custom_fonts() {
		$opt = get_option( self::CUSTOM_FONTS_OPTION, array() );
		if ( ! is_array( $opt ) ) {
			$opt = array();
		}
		return array(
			'items' => ( isset( $opt['items'] ) && is_array( $opt['items'] ) ) ? $opt['items'] : array(),
		);
	}

	/** Upsert a saved custom font by name. Same charset as sanitize_design's
	 * custom_heading/custom_body: letters/digits/spaces/hyphens, so Adobe's
	 * kebab-case slugs (e.g. "forma-djr-deck") survive intact. */
	public static function save_custom_font( $name, $family, $source ) {
		$name   = trim( sanitize_text_field( (string) $name ) );
		$family = trim( preg_replace( '/[^A-Za-z0-9 \-]/', '', (string) $family ) );
		if ( '' === $name || '' === $family ) {
			return false;
		}
		$opt = self::get_custom_fonts();
		$opt['items'][ $name ] = array(
			'family' => substr( $family, 0, 50 ),
			'source' => ( 'adobe' === $source ) ? 'adobe' : 'google',
		);
		update_option( self::CUSTOM_FONTS_OPTION, $opt, false );
		return true;
	}

	public static function delete_custom_font( $name ) {
		$opt = self::get_custom_fonts();
		unset( $opt['items'][ (string) $name ] );
		update_option( self::CUSTOM_FONTS_OPTION, $opt, false );
		return true;
	}

	// --- helpers ------------------------------------------------------------

	private static function decode_json( $raw, $default ) {
		if ( null === $raw || '' === $raw ) {
			return $default;
		}
		$decoded = json_decode( $raw, true );
		return ( null === $decoded ) ? $default : $decoded;
	}
}
