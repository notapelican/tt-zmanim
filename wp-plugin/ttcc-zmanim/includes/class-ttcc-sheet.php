<?php
/**
 * Sheet assembly helper.
 *
 * The engine's override mechanism edits printed *lines* (keyed by rule_id) and
 * is applied inside the service's /generate. Block-level *notes* are not lines,
 * so the engine can't edit them — this class applies note add/remove edits
 * plugin-side to the generated doc before rendering. That keeps the service a
 * pure pass-through and the note-editing UX entirely in WordPress.
 *
 * Stored per-sheet override shape:
 *   {
 *     "lines": { "<rule_id>": {"time":"19:15"} | {"suppress":true}, "add:<id>": {..line..} },
 *     "notes": { "<block_key>": { "removed": [int,...], "added": ["text",...] } }
 *   }
 *
 * @package TTCC_Zmanim
 */

defined( 'ABSPATH' ) || exit;

class TTCC_Zmanim_Sheet {

	/**
	 * Generate a doc for a date range and apply the stored overrides.
	 * Returns array{doc:array, engine_version:string} or WP_Error.
	 */
	public static function build( $start, $end, $overrides ) {
		$overrides = is_array( $overrides ) ? $overrides : array();
		$lines     = isset( $overrides['lines'] ) && is_array( $overrides['lines'] ) ? $overrides['lines'] : array();
		$notes     = isset( $overrides['notes'] ) && is_array( $overrides['notes'] ) ? $overrides['notes'] : array();

		$set      = TTCC_Zmanim_Storage::get_active_profile_set();
		$profiles = $set && ! empty( $set['profiles'] ) ? $set['profiles'] : null;
		$note_lib = $set && ! empty( $set['notes'] ) ? $set['notes'] : null;

		$doc = TTCC_Zmanim_Service_Client::generate( $start, $end, $lines, $profiles, $note_lib );
		if ( is_wp_error( $doc ) ) {
			return $doc;
		}
		$engine_version = isset( $doc['engine_version'] ) ? (string) $doc['engine_version'] : '';
		unset( $doc['engine_version'] );

		$doc = self::apply_note_edits( $doc, $notes );

		return array( 'doc' => $doc, 'engine_version' => $engine_version );
	}

	/** Whitelisted font keys the modern renderer accepts. */
	const FONT_KEYS = array( 'palatino', 'georgia', 'garamond', 'times', 'system', 'helvetica' );

	/**
	 * Pull the (sanitized) modern-layout design out of a stored overrides blob.
	 * Returns {template, logo?, heading_font?, body_font?, base?, text_color?,
	 * callout_bg?, callout_text?}. Colors must be hex, fonts must be whitelisted,
	 * base is clamped — defense in depth alongside the service's own sanitizing.
	 */
	public static function design_from_overrides( $overrides ) {
		$o        = is_array( $overrides ) ? $overrides : array();
		$template = ( isset( $o['template'] ) && 'modern' === $o['template'] ) ? 'modern' : 'classic';
		$d        = ( isset( $o['design'] ) && is_array( $o['design'] ) ) ? $o['design'] : array();
		return array( 'template' => $template ) + self::sanitize_design( $d );
	}

	/**
	 * Sanitize a design dict (whitelist fonts, clamp sizes, enum aligns, hex
	 * colors) preserving its nested shape. Shared by design_from_overrides and
	 * the style-preset store so both apply the identical whitelist.
	 */
	public static function sanitize_design( $d ) {
		$d   = is_array( $d ) ? $d : array();
		$out = array();

		if ( ! empty( $d['logo'] ) ) {
			$out['logo'] = esc_url_raw( (string) $d['logo'] );
		}
		foreach ( array( 'heading_font', 'body_font' ) as $k ) {
			if ( isset( $d[ $k ] ) && in_array( $d[ $k ], self::FONT_KEYS, true ) ) {
				$out[ $k ] = $d[ $k ];
			}
		}
		// Letters/digits/spaces/hyphens: Adobe Fonts (Typekit) kits declare their
		// families as kebab-case slugs (e.g. "forma-djr-deck"), not the display
		// name shown in the UI, so hyphens must survive sanitizing.
		foreach ( array( 'custom_heading', 'custom_body' ) as $k ) {
			if ( ! empty( $d[ $k ] ) ) {
				$name = trim( preg_replace( '/[^A-Za-z0-9 \-]/', '', (string) $d[ $k ] ) );
				if ( '' !== $name ) {
					$out[ $k ] = substr( $name, 0, 50 );
				}
			}
		}
		if ( isset( $d['font_source'] ) && 'adobe' === $d['font_source'] ) {
			$out['font_source'] = 'adobe';
		}
		if ( isset( $d['base'] ) && is_numeric( $d['base'] ) ) {
			$out['base'] = max( 8, min( 40, (float) $d['base'] ) );
		}
		// Per-type typography: header (name line) and subheader (location line)
		// each carry an optional font, size (px) and justification; blank keeps
		// the layout's default. Logo size is modern-only.
		foreach ( array( 'header', 'subheader' ) as $t ) {
			if ( isset( $d[ $t . '_font' ] ) && in_array( $d[ $t . '_font' ], self::FONT_KEYS, true ) ) {
				$out[ $t . '_font' ] = $d[ $t . '_font' ];
			}
			if ( isset( $d[ $t . '_size' ] ) && is_numeric( $d[ $t . '_size' ] ) && $d[ $t . '_size' ] > 0 ) {
				$out[ $t . '_size' ] = max( 8, min( 48, (float) $d[ $t . '_size' ] ) );
			}
			if ( isset( $d[ $t . '_align' ] ) && in_array( $d[ $t . '_align' ], array( 'left', 'center', 'right' ), true ) ) {
				$out[ $t . '_align' ] = $d[ $t . '_align' ];
			}
			// Optional custom web-font family (saved Google name or Adobe slug);
			// same charset as custom_heading/custom_body so hyphens survive.
			if ( ! empty( $d[ $t . '_custom' ] ) ) {
				$name = trim( preg_replace( '/[^A-Za-z0-9 \-]/', '', (string) $d[ $t . '_custom' ] ) );
				if ( '' !== $name ) {
					$out[ $t . '_custom' ] = substr( $name, 0, 50 );
				}
			}
		}
		if ( isset( $d['logo_size'] ) && is_numeric( $d['logo_size'] ) && $d['logo_size'] > 0 ) {
			$out['logo_size'] = max( 20, min( 140, (float) $d['logo_size'] ) );
		}
		// בס״ד marker font/size (px) and page-edge margin (mm); blank = defaults.
		if ( isset( $d['bsd_font'] ) && in_array( $d['bsd_font'], self::FONT_KEYS, true ) ) {
			$out['bsd_font'] = $d['bsd_font'];
		}
		if ( ! empty( $d['bsd_custom'] ) ) {
			$name = trim( preg_replace( '/[^A-Za-z0-9 \-]/', '', (string) $d['bsd_custom'] ) );
			if ( '' !== $name ) {
				$out['bsd_custom'] = substr( $name, 0, 50 );
			}
		}
		if ( isset( $d['bsd_size'] ) && is_numeric( $d['bsd_size'] ) && $d['bsd_size'] > 0 ) {
			$out['bsd_size'] = max( 6, min( 36, (float) $d['bsd_size'] ) );
		}
		if ( isset( $d['page_margin'] ) && is_numeric( $d['page_margin'] ) && $d['page_margin'] > 0 ) {
			$out['page_margin'] = max( 4, min( 25, (float) $d['page_margin'] ) );
		}
		// Content sizing: 'fixed' makes the base size drive the text (fit only
		// shrinks to avoid overflow); anything else = 'fill' (auto fit-to-page).
		if ( isset( $d['fit_mode'] ) && 'fixed' === $d['fit_mode'] ) {
			$out['fit_mode'] = 'fixed';
		}
		foreach ( array( 'text_color', 'callout_bg', 'callout_text' ) as $k ) {
			if ( isset( $d[ $k ] ) && preg_match( '/^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/', (string) $d[ $k ] ) ) {
				$out[ $k ] = $d[ $k ];
			}
		}
		return $out;
	}

	/**
	 * A stable key identifying a block for note edits: week blocks by their
	 * Sunday (civil_start), day blocks by their date.
	 */
	public static function block_key( $block ) {
		if ( isset( $block['type'] ) && 'day' === $block['type'] ) {
			return 'day:' . ( isset( $block['date'] ) ? $block['date'] : '' );
		}
		return 'week:' . ( isset( $block['civil_start'] ) ? $block['civil_start'] : '' );
	}

	/**
	 * Apply per-block note edits: drop removed indices (relative to the engine's
	 * original notes order), then append sanitized free-text additions.
	 */
	public static function apply_note_edits( $doc, $note_edits ) {
		if ( empty( $doc['blocks'] ) || ! is_array( $doc['blocks'] ) ) {
			return $doc;
		}
		foreach ( $doc['blocks'] as &$block ) {
			$key    = self::block_key( $block );
			$orig   = isset( $block['notes'] ) && is_array( $block['notes'] ) ? array_values( $block['notes'] ) : array();
			$edit   = isset( $note_edits[ $key ] ) && is_array( $note_edits[ $key ] ) ? $note_edits[ $key ] : array();
			$removed = isset( $edit['removed'] ) && is_array( $edit['removed'] ) ? array_map( 'intval', $edit['removed'] ) : array();
			$added   = isset( $edit['added'] ) && is_array( $edit['added'] ) ? $edit['added'] : array();

			$kept = array();
			foreach ( $orig as $i => $text ) {
				if ( ! in_array( $i, $removed, true ) ) {
					$kept[] = $text;
				}
			}
			foreach ( $added as $text ) {
				$text = trim( wp_strip_all_tags( (string) $text ) );
				if ( '' !== $text ) {
					$kept[] = $text;
				}
			}
			$block['notes'] = $kept;
		}
		unset( $block );
		return $doc;
	}
}
