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

	/** Modern-layout defaults new sheets inherit (localized to the dashboard). */
	public static function design_defaults() {
		return array(
			'template'     => 'modern' === self::get( 'default_template', 'classic' ) ? 'modern' : 'classic',
			'logo'         => (string) self::get( 'default_logo', '' ),
			'heading_font' => (string) self::get( 'default_heading_font', 'palatino' ),
			'body_font'    => (string) self::get( 'default_body_font', 'system' ),
			'base'         => (int) self::get( 'default_base', 15 ),
			// Per-type typography (blank = the layout's built-in default).
			'header_font'     => (string) self::get( 'default_header_font', '' ),
			'header_size'     => (string) self::get( 'default_header_size', '' ),
			'header_align'    => (string) self::get( 'default_header_align', '' ),
			'subheader_font'  => (string) self::get( 'default_subheader_font', '' ),
			'subheader_size'  => (string) self::get( 'default_subheader_size', '' ),
			'subheader_align' => (string) self::get( 'default_subheader_align', '' ),
			'logo_size'       => (string) self::get( 'default_logo_size', '' ),
			'bsd_size'        => (string) self::get( 'default_bsd_size', '' ),
			'page_margin'     => (string) self::get( 'default_page_margin', '' ),
			'text_color'   => (string) self::get( 'default_text_color', '#1b1e28' ),
			'callout_bg'   => (string) self::get( 'default_callout_bg', '#fbeef1' ),
			'callout_text' => (string) self::get( 'default_callout_text', '#a3324b' ),
		);
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

		// Modern-layout design defaults.
		$out['default_template'] = ( isset( $input['default_template'] ) && 'modern' === $input['default_template'] ) ? 'modern' : 'classic';
		$out['default_logo']     = isset( $input['default_logo'] ) ? esc_url_raw( trim( $input['default_logo'] ) ) : '';
		$fonts = TTCC_Zmanim_Sheet::FONT_KEYS;
		$out['default_heading_font'] = ( isset( $input['default_heading_font'] ) && in_array( $input['default_heading_font'], $fonts, true ) ) ? $input['default_heading_font'] : 'palatino';
		$out['default_body_font']    = ( isset( $input['default_body_font'] ) && in_array( $input['default_body_font'], $fonts, true ) ) ? $input['default_body_font'] : 'system';
		$base = isset( $input['default_base'] ) ? (int) $input['default_base'] : 15;
		$out['default_base'] = max( 8, min( 40, $base ) );
		foreach ( array( 'default_text_color' => '#1b1e28', 'default_callout_bg' => '#fbeef1', 'default_callout_text' => '#a3324b' ) as $key => $fallback ) {
			$val = isset( $input[ $key ] ) ? (string) $input[ $key ] : '';
			$out[ $key ] = preg_match( '/^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/', $val ) ? $val : $fallback;
		}
		// Export sizing: 'fit' (default — exports match the preview's
		// fit-to-page scaling) or 'natural' (no scaling; may overflow pages).
		$out['export_fit'] = ( isset( $input['export_fit'] ) && 'natural' === $input['export_fit'] ) ? 'natural' : 'fit';
		// Adobe Fonts (Typekit) web-project id — site-level; lowercase alnum.
		$out['adobe_kit'] = isset( $input['adobe_kit'] ) ? substr( preg_replace( '/[^a-z0-9]/', '', strtolower( (string) $input['adobe_kit'] ) ), 0, 20 ) : '';
		// GitHub token for over-the-air plugin updates from the private repo.
		$out['github_token'] = isset( $input['github_token'] ) ? sanitize_text_field( trim( (string) $input['github_token'] ) ) : '';
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
					<tr>
						<th scope="row"><label for="ttcc_github_token"><?php esc_html_e( 'GitHub update token', 'ttcc-zmanim' ); ?></label></th>
						<td>
							<input name="<?php echo esc_attr( self::OPTION ); ?>[github_token]" id="ttcc_github_token" type="password"
								class="regular-text" value="<?php echo esc_attr( isset( $opts['github_token'] ) ? $opts['github_token'] : '' ); ?>"
								autocomplete="off" />
							<p class="description"><?php esc_html_e( 'Enables one-click plugin updates from the private GitHub repo. Use a fine-grained personal access token with read-only Contents access to notapelican/tt-zmanim. Leave blank to disable OTA updates.', 'ttcc-zmanim' ); ?></p>
						</td>
					</tr>
					<tr>
						<th scope="row"><label for="ttcc_export_fit"><?php esc_html_e( 'Export sizing', 'ttcc-zmanim' ); ?></label></th>
						<td>
							<select id="ttcc_export_fit" name="<?php echo esc_attr( self::OPTION ); ?>[export_fit]">
								<option value="fit" <?php selected( self::get( 'export_fit', 'fit' ), 'fit' ); ?>><?php esc_html_e( 'Fit to page (default — matches the preview)', 'ttcc-zmanim' ); ?></option>
								<option value="natural" <?php selected( self::get( 'export_fit', 'fit' ), 'natural' ); ?>><?php esc_html_e( 'Natural size (no fit-to-page scaling)', 'ttcc-zmanim' ); ?></option>
							</select>
							<p class="description"><?php esc_html_e( 'PDF/PNG exports are scaled to fill each A4 page exactly like the preview. Choose "Natural size" to export at 100% instead.', 'ttcc-zmanim' ); ?></p>
						</td>
					</tr>
					<?php if ( $sig_url ) : ?>
					<tr>
						<th scope="row"><?php esc_html_e( 'piSignage URL', 'ttcc-zmanim' ); ?></th>
						<td><code><?php echo esc_html( $sig_url ); ?></code>
							<p class="description"><?php esc_html_e( 'Public current-week signage page (unguessable slug). Point the piSignage screen here.', 'ttcc-zmanim' ); ?></p>
						</td>
					</tr>
					<tr>
						<th scope="row"><?php esc_html_e( 'piSignage URL — Shabbos screen', 'ttcc-zmanim' ); ?></th>
						<td><code><?php echo esc_html( $sig_url . 'shabbos/' ); ?></code>
							<p class="description"><?php esc_html_e( 'Large-type Shabbos & Yom Tov screen (candle lighting, ends, fasts) for a portrait 1080×1920 display. Self-refreshing; keeps the last-good times if the connection drops.', 'ttcc-zmanim' ); ?></p>
						</td>
					</tr>
					<?php endif; ?>
				</table>

				<h2><?php esc_html_e( 'Modern layout — defaults', 'ttcc-zmanim' ); ?></h2>
				<p class="description"><?php esc_html_e( 'Starting design for new sheets. Each sheet can override these in the dashboard.', 'ttcc-zmanim' ); ?></p>
				<?php
				$d      = self::design_defaults();
				$fields = self::OPTION;
				$fonts  = array(
					'palatino'  => __( 'Palatino (serif)', 'ttcc-zmanim' ),
					'georgia'   => __( 'Georgia (serif)', 'ttcc-zmanim' ),
					'garamond'  => __( 'Garamond (serif)', 'ttcc-zmanim' ),
					'times'     => __( 'Times New Roman', 'ttcc-zmanim' ),
					'system'    => __( 'System sans', 'ttcc-zmanim' ),
					'helvetica' => __( 'Helvetica / Arial', 'ttcc-zmanim' ),
				);
				?>
				<table class="form-table" role="presentation">
					<tr>
						<th scope="row"><?php esc_html_e( 'Default layout', 'ttcc-zmanim' ); ?></th>
						<td>
							<select name="<?php echo esc_attr( $fields ); ?>[default_template]">
								<option value="classic" <?php selected( $d['template'], 'classic' ); ?>><?php esc_html_e( 'Classic', 'ttcc-zmanim' ); ?></option>
								<option value="modern" <?php selected( $d['template'], 'modern' ); ?>><?php esc_html_e( 'Modern', 'ttcc-zmanim' ); ?></option>
							</select>
						</td>
					</tr>
					<tr>
						<th scope="row"><label for="ttcc_default_logo"><?php esc_html_e( 'Default logo URL', 'ttcc-zmanim' ); ?></label></th>
						<td>
							<input type="url" id="ttcc_default_logo" name="<?php echo esc_attr( $fields ); ?>[default_logo]" class="regular-text" value="<?php echo esc_attr( $d['logo'] ); ?>" placeholder="https://ttcc.org.au/logo.png" />
							<p class="description"><?php esc_html_e( 'Upload the logo to the Media Library and paste its URL. Per-sheet, you can pick a different logo from the dashboard.', 'ttcc-zmanim' ); ?></p>
						</td>
					</tr>
					<tr>
						<th scope="row"><?php esc_html_e( 'Fonts', 'ttcc-zmanim' ); ?></th>
						<td>
							<label><?php esc_html_e( 'Heading', 'ttcc-zmanim' ); ?>
								<select name="<?php echo esc_attr( $fields ); ?>[default_heading_font]">
									<?php foreach ( $fonts as $k => $label ) : ?>
										<option value="<?php echo esc_attr( $k ); ?>" <?php selected( $d['heading_font'], $k ); ?>><?php echo esc_html( $label ); ?></option>
									<?php endforeach; ?>
								</select>
							</label>
							&nbsp;
							<label><?php esc_html_e( 'Body', 'ttcc-zmanim' ); ?>
								<select name="<?php echo esc_attr( $fields ); ?>[default_body_font]">
									<?php foreach ( $fonts as $k => $label ) : ?>
										<option value="<?php echo esc_attr( $k ); ?>" <?php selected( $d['body_font'], $k ); ?>><?php echo esc_html( $label ); ?></option>
									<?php endforeach; ?>
								</select>
							</label>
						</td>
					</tr>
					<tr>
						<th scope="row"><label for="ttcc_default_base"><?php esc_html_e( 'Base text size', 'ttcc-zmanim' ); ?></label></th>
						<td><input type="number" id="ttcc_default_base" name="<?php echo esc_attr( $fields ); ?>[default_base]" min="8" max="40" value="<?php echo esc_attr( $d['base'] ); ?>" /> px</td>
					</tr>
					<tr>
						<th scope="row"><label for="ttcc_adobe_kit"><?php esc_html_e( 'Adobe Fonts Web Project ID', 'ttcc-zmanim' ); ?></label></th>
						<td>
							<input type="text" id="ttcc_adobe_kit" name="<?php echo esc_attr( $fields ); ?>[adobe_kit]" class="regular-text" value="<?php echo esc_attr( self::get( 'adobe_kit', '' ) ); ?>" placeholder="abc1def" />
							<p class="description"><?php esc_html_e( 'From your Adobe Fonts Web Project (the id in use.typekit.net/ID.css). Add this site\'s domain to the project\'s allowed domains. Then on a sheet, set Font source = Adobe and type the family name.', 'ttcc-zmanim' ); ?></p>
						</td>
					</tr>
					<tr>
						<th scope="row"><?php esc_html_e( 'Colors', 'ttcc-zmanim' ); ?></th>
						<td>
							<label><?php esc_html_e( 'Text', 'ttcc-zmanim' ); ?>
								<input type="color" name="<?php echo esc_attr( $fields ); ?>[default_text_color]" value="<?php echo esc_attr( $d['text_color'] ); ?>" /></label>
							&nbsp;
							<label><?php esc_html_e( 'Note box', 'ttcc-zmanim' ); ?>
								<input type="color" name="<?php echo esc_attr( $fields ); ?>[default_callout_bg]" value="<?php echo esc_attr( $d['callout_bg'] ); ?>" /></label>
							&nbsp;
							<label><?php esc_html_e( 'Note text', 'ttcc-zmanim' ); ?>
								<input type="color" name="<?php echo esc_attr( $fields ); ?>[default_callout_text]" value="<?php echo esc_attr( $d['callout_text'] ); ?>" /></label>
						</td>
					</tr>
				</table>
				<?php submit_button(); ?>
			</form>
		</div>
		<?php
	}
}
