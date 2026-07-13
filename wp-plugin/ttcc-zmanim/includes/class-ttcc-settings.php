<?php
/**
 * Plugin settings: the sheet-service base URL and shared-secret token, plus a
 * piSignage slug. Stored as a single option array. Renders a Settings page.
 *
 * @package TTCC_Zmanim
 */

defined( 'ABSPATH' ) || exit;

class TTCC_Zmanim_Settings {

	const OPTION = 'ttcc_zmanim_settings';

	public static function get( $key, $default = '' ) {
		$opts = get_option( self::OPTION, array() );
		return isset( $opts[ $key ] ) ? $opts[ $key ] : $default;
	}

	public static function service_url() {
		return untrailingslashit( (string) self::get( 'service_url', '' ) );
	}

	public static function service_token() {
		return (string) self::get( 'service_token', '' );
	}

	/**
	 * Slug for the public piSignage page. Random on first save so the URL is
	 * unguessable; the admin can view it on the Settings page.
	 */
	public static function pisignage_slug() {
		$slug = (string) self::get( 'pisignage_slug', '' );
		return $slug;
	}

	public static function register() {
		register_setting(
			'ttcc_zmanim',
			self::OPTION,
			array( 'sanitize_callback' => array( __CLASS__, 'sanitize' ) )
		);
	}

	public static function sanitize( $input ) {
		$out                   = array();
		$out['service_url']    = isset( $input['service_url'] ) ? esc_url_raw( trim( $input['service_url'] ) ) : '';
		$out['service_token']  = isset( $input['service_token'] ) ? sanitize_text_field( $input['service_token'] ) : '';
		$existing_slug         = self::pisignage_slug();
		$out['pisignage_slug'] = $existing_slug ? $existing_slug : wp_generate_password( 20, false, false );
		return $out;
	}

	public static function render_page() {
		if ( ! current_user_can( TTCC_ZMANIM_CAP ) ) {
			wp_die( esc_html__( 'You do not have permission to manage TTCC timesheets.', 'ttcc-zmanim' ) );
		}
		$health   = TTCC_Zmanim_Service_Client::health();
		$slug     = self::pisignage_slug();
		$sig_url  = $slug ? home_url( '/ttcc-signage/' . $slug . '/' ) : '';
		?>
		<div class="wrap">
			<h1><?php esc_html_e( 'TTCC Timesheets — Settings', 'ttcc-zmanim' ); ?></h1>

			<div class="ttcc-health notice <?php echo $health['ok'] ? 'notice-success' : 'notice-error'; ?>" style="padding:10px 12px;">
				<?php if ( $health['ok'] ) : ?>
					<strong><?php esc_html_e( 'Sheet service: online', 'ttcc-zmanim' ); ?></strong>
					— <?php echo esc_html( sprintf( 'engine %s', $health['engine_version'] ) ); ?>
					<?php echo $health['chromium'] ? '· ' . esc_html__( 'Chromium available (PDF/PNG export ready)', 'ttcc-zmanim' ) : '· ' . esc_html__( 'Chromium NOT available (PDF/PNG export will fail)', 'ttcc-zmanim' ); ?>
				<?php else : ?>
					<strong><?php esc_html_e( 'Sheet service: OFFLINE', 'ttcc-zmanim' ); ?></strong>
					— <?php echo esc_html( $health['error'] ); ?>.
					<?php esc_html_e( 'Generating and editing are unavailable until it is reachable.', 'ttcc-zmanim' ); ?>
				<?php endif; ?>
			</div>

			<form method="post" action="options.php">
				<?php settings_fields( 'ttcc_zmanim' ); ?>
				<?php $opts = get_option( self::OPTION, array() ); ?>
				<table class="form-table" role="presentation">
					<tr>
						<th scope="row"><label for="ttcc_service_url"><?php esc_html_e( 'Sheet service URL', 'ttcc-zmanim' ); ?></label></th>
						<td>
							<input name="<?php echo esc_attr( self::OPTION ); ?>[service_url]" id="ttcc_service_url" type="url"
								class="regular-text" value="<?php echo esc_attr( isset( $opts['service_url'] ) ? $opts['service_url'] : '' ); ?>"
								placeholder="https://sheets.example.org" />
							<p class="description"><?php esc_html_e( 'Base URL of the Python sheet service (runs off SiteGround). HTTPS strongly recommended.', 'ttcc-zmanim' ); ?></p>
						</td>
					</tr>
					<tr>
						<th scope="row"><label for="ttcc_service_token"><?php esc_html_e( 'Service token', 'ttcc-zmanim' ); ?></label></th>
						<td>
							<input name="<?php echo esc_attr( self::OPTION ); ?>[service_token]" id="ttcc_service_token" type="password"
								class="regular-text" value="<?php echo esc_attr( isset( $opts['service_token'] ) ? $opts['service_token'] : '' ); ?>"
								autocomplete="off" />
							<p class="description"><?php esc_html_e( 'Shared secret (matches TTCC_SERVICE_TOKEN on the service). Sent as a bearer token; never exposed to the browser.', 'ttcc-zmanim' ); ?></p>
						</td>
					</tr>
					<?php if ( $sig_url ) : ?>
					<tr>
						<th scope="row"><?php esc_html_e( 'piSignage URL', 'ttcc-zmanim' ); ?></th>
						<td><code><?php echo esc_html( $sig_url ); ?></code>
							<p class="description"><?php esc_html_e( 'Public current-week signage page (unguessable slug). Point the piSignage screen here.', 'ttcc-zmanim' ); ?></p>
						</td>
					</tr>
					<?php endif; ?>
				</table>
				<?php submit_button(); ?>
			</form>
		</div>
		<?php
	}
}
