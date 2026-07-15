<?php
/**
 * Uninstall cleanup: drop custom tables and options. Runs only on real plugin
 * deletion (not deactivation).
 *
 * @package TTCC_Zmanim
 */

defined( 'WP_UNINSTALL_PLUGIN' ) || exit;

global $wpdb;

$tables = array(
	$wpdb->prefix . 'ttcc_timesheets',
	$wpdb->prefix . 'ttcc_profile_sets',
);
foreach ( $tables as $t ) {
	// phpcs:ignore WordPress.DB.PreparedSQL.NotPrepared -- table names are internal constants.
	$wpdb->query( "DROP TABLE IF EXISTS {$t}" );
}

delete_option( 'ttcc_zmanim_settings' );
delete_option( 'ttcc_zmanim_presets' );

// Remove persistent last-good public caches (option keys prefixed ttcc_lastgood_).
// phpcs:ignore WordPress.DB.DirectDatabaseQuery
$wpdb->query( "DELETE FROM {$wpdb->options} WHERE option_name LIKE 'ttcc_lastgood_%'" );

// Drop the custom capability from administrators.
$role = get_role( 'administrator' );
if ( $role ) {
	$role->remove_cap( 'manage_ttcc_timesheets' );
}
