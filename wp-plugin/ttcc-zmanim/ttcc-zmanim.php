<?php
/**
 * Plugin Name:       TTCC Zmanim Timesheets
 * Description:        Generate, edit and publish the TTCC weekly/yom-tov times sheets. Wraps the fixture-validated Python zmanim engine via an HTTP sheet service (see service/). Halachic times are computed by the engine and never recomputed here.
 * Version:           0.3.0
 * Requires PHP:      7.4
 * Requires at least: 6.0
 * Author:            Tzemach Tzedek Community Centre
 * Text Domain:       ttcc-zmanim
 *
 * @package TTCC_Zmanim
 */

defined( 'ABSPATH' ) || exit;

define( 'TTCC_ZMANIM_VERSION', '0.3.0' );
define( 'TTCC_ZMANIM_FILE', __FILE__ );
define( 'TTCC_ZMANIM_DIR', plugin_dir_path( __FILE__ ) );
define( 'TTCC_ZMANIM_URL', plugin_dir_url( __FILE__ ) );
define( 'TTCC_ZMANIM_CAP', 'manage_ttcc_timesheets' );

require_once TTCC_ZMANIM_DIR . 'includes/class-ttcc-storage.php';
require_once TTCC_ZMANIM_DIR . 'includes/class-ttcc-settings.php';
require_once TTCC_ZMANIM_DIR . 'includes/class-ttcc-service-client.php';
require_once TTCC_ZMANIM_DIR . 'includes/class-ttcc-sheet.php';
require_once TTCC_ZMANIM_DIR . 'includes/class-ttcc-rest.php';
require_once TTCC_ZMANIM_DIR . 'includes/class-ttcc-admin.php';
require_once TTCC_ZMANIM_DIR . 'includes/class-ttcc-public.php';
require_once TTCC_ZMANIM_DIR . 'includes/class-ttcc-updater.php';
require_once TTCC_ZMANIM_DIR . 'includes/class-ttcc-plugin.php';

// Over-the-air updates from GitHub releases (see class-ttcc-updater.php).
TTCC_Zmanim_Updater::init();

// Activation: create tables, grant the capability to administrators, seed the
// profile set (best-effort — needs the service reachable; safe to retry later).
register_activation_hook( __FILE__, array( 'TTCC_Zmanim_Plugin', 'activate' ) );
register_deactivation_hook( __FILE__, array( 'TTCC_Zmanim_Plugin', 'deactivate' ) );

add_action( 'plugins_loaded', array( 'TTCC_Zmanim_Plugin', 'instance' ) );
