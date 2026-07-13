<?php
/**
 * HTTP client for the Python sheet service. Uses the WordPress HTTP API and
 * sends the shared secret as a bearer token. The token never reaches the
 * browser — all service calls are server-side from PHP.
 *
 * @package TTCC_Zmanim
 */

defined( 'ABSPATH' ) || exit;

class TTCC_Zmanim_Service_Client {

	/** Request timeout (seconds). Rasterization can take a few seconds. */
	const TIMEOUT = 30;

	private static function url( $path ) {
		return TTCC_Zmanim_Settings::service_url() . $path;
	}

	private static function auth_headers( $extra = array() ) {
		$token = TTCC_Zmanim_Settings::service_token();
		$h     = array( 'Content-Type' => 'application/json' );
		if ( $token ) {
			$h['Authorization'] = 'Bearer ' . $token;
		}
		return array_merge( $h, $extra );
	}

	/**
	 * GET /health. Returns array{ok:bool, engine_version:string, chromium:bool, error:string}.
	 */
	public static function health() {
		$base = TTCC_Zmanim_Settings::service_url();
		if ( ! $base ) {
			return array( 'ok' => false, 'error' => __( 'service URL not configured', 'ttcc-zmanim' ), 'engine_version' => '', 'chromium' => false );
		}
		$res = wp_remote_get( self::url( '/health' ), array( 'timeout' => 8 ) );
		if ( is_wp_error( $res ) ) {
			return array( 'ok' => false, 'error' => $res->get_error_message(), 'engine_version' => '', 'chromium' => false );
		}
		if ( 200 !== (int) wp_remote_retrieve_response_code( $res ) ) {
			return array( 'ok' => false, 'error' => 'HTTP ' . wp_remote_retrieve_response_code( $res ), 'engine_version' => '', 'chromium' => false );
		}
		$body = json_decode( wp_remote_retrieve_body( $res ), true );
		return array(
			'ok'             => true,
			'error'          => '',
			'engine_version' => isset( $body['engine_version'] ) ? (string) $body['engine_version'] : '',
			'chromium'       => ! empty( $body['chromium'] ),
		);
	}

	/**
	 * POST a JSON body, decode a JSON response. Returns array or WP_Error.
	 */
	private static function post_json( $path, $payload ) {
		$base = TTCC_Zmanim_Settings::service_url();
		if ( ! $base ) {
			return new WP_Error( 'ttcc_no_service', __( 'Sheet service URL is not configured.', 'ttcc-zmanim' ) );
		}
		$res = wp_remote_post(
			self::url( $path ),
			array(
				'timeout' => self::TIMEOUT,
				'headers' => self::auth_headers(),
				'body'    => wp_json_encode( $payload ),
			)
		);
		if ( is_wp_error( $res ) ) {
			return $res;
		}
		$code = (int) wp_remote_retrieve_response_code( $res );
		$body = wp_remote_retrieve_body( $res );
		if ( $code < 200 || $code >= 300 ) {
			return new WP_Error( 'ttcc_service_http', self::error_detail( $body, $code ), array( 'status' => $code ) );
		}
		$decoded = json_decode( $body, true );
		if ( null === $decoded ) {
			return new WP_Error( 'ttcc_service_json', __( 'Malformed response from sheet service.', 'ttcc-zmanim' ) );
		}
		return $decoded;
	}

	/**
	 * POST expecting a binary body (PDF/PNG/DOCX). Returns array{body, content_type} or WP_Error.
	 */
	private static function post_binary( $path, $payload ) {
		$base = TTCC_Zmanim_Settings::service_url();
		if ( ! $base ) {
			return new WP_Error( 'ttcc_no_service', __( 'Sheet service URL is not configured.', 'ttcc-zmanim' ) );
		}
		$res = wp_remote_post(
			self::url( $path ),
			array(
				'timeout' => self::TIMEOUT,
				'headers' => self::auth_headers(),
				'body'    => wp_json_encode( $payload ),
			)
		);
		if ( is_wp_error( $res ) ) {
			return $res;
		}
		$code = (int) wp_remote_retrieve_response_code( $res );
		$body = wp_remote_retrieve_body( $res );
		if ( $code < 200 || $code >= 300 ) {
			return new WP_Error( 'ttcc_service_http', self::error_detail( $body, $code ), array( 'status' => $code ) );
		}
		return array(
			'body'         => $body,
			'content_type' => wp_remote_retrieve_header( $res, 'content-type' ),
		);
	}

	private static function error_detail( $body, $code ) {
		$decoded = json_decode( $body, true );
		if ( is_array( $decoded ) && isset( $decoded['detail'] ) ) {
			$detail = is_array( $decoded['detail'] ) ? wp_json_encode( $decoded['detail'] ) : $decoded['detail'];
			return sprintf( 'service HTTP %d: %s', $code, $detail );
		}
		return sprintf( 'service HTTP %d', $code );
	}

	// --- typed endpoints ----------------------------------------------------

	/**
	 * POST /generate. $overrides is the flat rule_id override dict (line edits
	 * only — note edits are applied plugin-side, see TTCC_Zmanim_Sheet).
	 */
	public static function generate( $start, $end, $overrides = null, $profiles = null, $notes = null ) {
		$payload = array( 'start' => $start, 'end' => $end );
		if ( null !== $overrides ) {
			$payload['overrides'] = $overrides ? $overrides : (object) array();
		}
		if ( null !== $profiles ) {
			$payload['profiles'] = $profiles;
		}
		if ( null !== $notes ) {
			$payload['notes'] = $notes;
		}
		return self::post_json( '/generate', $payload );
	}

	/**
	 * Build the render payload for a pre-generated doc, adding the modern
	 * template's logo/theme when requested. $design is the per-sheet design
	 * array: {template, logo, ...theme fields}. docx has no modern renderer, so
	 * it always renders classic.
	 */
	private static function render_payload( $doc, $variant, $design, $allow_modern = true ) {
		$payload = array( 'doc' => $doc, 'variant' => $variant );
		$design  = is_array( $design ) ? $design : array();
		$template = ( $allow_modern && isset( $design['template'] ) && 'modern' === $design['template'] ) ? 'modern' : 'classic';
		$payload['template'] = $template;
		if ( 'modern' === $template ) {
			if ( ! empty( $design['logo'] ) ) {
				$payload['logo_url'] = (string) $design['logo'];
			}
			$theme = array();
			foreach ( array( 'heading_font', 'body_font', 'custom_heading', 'custom_body', 'font_source', 'base', 'text_color', 'callout_bg', 'callout_text' ) as $k ) {
				if ( isset( $design[ $k ] ) && '' !== $design[ $k ] ) {
					$theme[ $k ] = $design[ $k ];
				}
			}
			$kit = (string) TTCC_Zmanim_Settings::get( 'adobe_kit', '' );
			if ( '' !== $kit ) {
				$theme['adobe_kit'] = $kit;
			}
			if ( $theme ) {
				$payload['theme'] = $theme;
			}
			// Referer = the site domain so a domain-locked Adobe Fonts kit serves
			// during the headless PDF/PNG render.
			$payload['referer'] = home_url();
		}
		return $payload;
	}

	/** POST /render/html with a pre-generated doc. Returns array{html, engine_version} or WP_Error. */
	public static function render_html_doc( $doc, $variant = 'print', $design = null ) {
		return self::post_json( '/render/html', self::render_payload( $doc, $variant, $design ) );
	}

	/** POST /render/{pdf|png|docx} with a pre-generated doc. Returns binary array or WP_Error. */
	public static function render_binary( $kind, $doc, $variant = 'print', $design = null ) {
		$path = '/render/' . $kind;
		// The modern layout is HTML-based; .docx keeps the classic renderer.
		return self::post_binary( $path, self::render_payload( $doc, $variant, $design, 'docx' !== $kind ) );
	}

	/** POST /render/whatsapp with a pre-generated doc. Returns array{text, engine_version} or WP_Error. */
	public static function whatsapp_text( $doc ) {
		return self::post_json( '/render/whatsapp', array( 'doc' => $doc ) );
	}

	/** GET /profiles/default. Returns array{profiles, notes} or WP_Error. */
	public static function default_profiles() {
		$base = TTCC_Zmanim_Settings::service_url();
		if ( ! $base ) {
			return new WP_Error( 'ttcc_no_service', __( 'Sheet service URL is not configured.', 'ttcc-zmanim' ) );
		}
		$res = wp_remote_get(
			self::url( '/profiles/default' ),
			array( 'timeout' => self::TIMEOUT, 'headers' => self::auth_headers() )
		);
		if ( is_wp_error( $res ) ) {
			return $res;
		}
		$code = (int) wp_remote_retrieve_response_code( $res );
		if ( 200 !== $code ) {
			return new WP_Error( 'ttcc_service_http', self::error_detail( wp_remote_retrieve_body( $res ), $code ) );
		}
		return json_decode( wp_remote_retrieve_body( $res ), true );
	}
}
