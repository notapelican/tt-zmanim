<?php
/**
 * Dashboard view — a container the editor JS (admin/js/dashboard.js) drives.
 *
 * @package TTCC_Zmanim
 * @var int $edit_id  Timesheet id to load, or 0 for a fresh sheet.
 */

defined( 'ABSPATH' ) || exit;
?>
<div class="wrap ttcc-dashboard" id="ttcc-app" data-sheet-id="<?php echo esc_attr( (int) $edit_id ); ?>">
	<h1 class="wp-heading-inline"><?php esc_html_e( 'TTCC Timesheets', 'ttcc-zmanim' ); ?></h1>

	<div id="ttcc-health" class="ttcc-health" role="status" aria-live="polite"></div>

	<div class="ttcc-toolbar">
		<label><?php esc_html_e( 'Week of (Sunday)', 'ttcc-zmanim' ); ?>
			<input type="date" id="ttcc-start" />
		</label>
		<label><?php esc_html_e( 'Weeks', 'ttcc-zmanim' ); ?>
			<select id="ttcc-weeks">
				<option value="1"><?php esc_html_e( '1 week', 'ttcc-zmanim' ); ?></option>
				<option value="2"><?php esc_html_e( '2 weeks', 'ttcc-zmanim' ); ?></option>
				<option value="3"><?php esc_html_e( '3 weeks', 'ttcc-zmanim' ); ?></option>
				<option value="4"><?php esc_html_e( '4 weeks', 'ttcc-zmanim' ); ?></option>
				<option value="custom"><?php esc_html_e( 'Custom…', 'ttcc-zmanim' ); ?></option>
			</select>
		</label>
		<label><?php esc_html_e( 'Through', 'ttcc-zmanim' ); ?>
			<input type="date" id="ttcc-end" />
		</label>
		<label class="ttcc-title-field"><?php esc_html_e( 'Title', 'ttcc-zmanim' ); ?>
			<input type="text" id="ttcc-title" placeholder="<?php esc_attr_e( 'e.g. Vayeishev 5786', 'ttcc-zmanim' ); ?>" />
		</label>
		<button type="button" class="button button-primary" id="ttcc-generate"><?php esc_html_e( 'Generate', 'ttcc-zmanim' ); ?></button>
		<button type="button" class="button" id="ttcc-save"><?php esc_html_e( 'Save', 'ttcc-zmanim' ); ?></button>
		<select id="ttcc-status">
			<option value="draft"><?php esc_html_e( 'Draft', 'ttcc-zmanim' ); ?></option>
			<option value="final"><?php esc_html_e( 'Final', 'ttcc-zmanim' ); ?></option>
		</select>
		<span class="ttcc-spacer"></span>
		<span class="ttcc-page-toggle">
			<label><input type="checkbox" id="ttcc-pageguides" checked /> <?php esc_html_e( 'Show page boundaries', 'ttcc-zmanim' ); ?></label>
		</span>
	</div>

	<div class="ttcc-range-label" id="ttcc-range-label" role="status" aria-live="polite"></div>

	<div class="ttcc-toolbar ttcc-design-bar">
		<label><?php esc_html_e( 'Layout', 'ttcc-zmanim' ); ?>
			<select id="ttcc-layout">
				<option value="classic"><?php esc_html_e( 'Classic', 'ttcc-zmanim' ); ?></option>
				<option value="modern"><?php esc_html_e( 'Modern', 'ttcc-zmanim' ); ?></option>
			</select>
		</label>
		<div id="ttcc-design" class="ttcc-design" hidden>
			<span class="ttcc-logo-field">
				<span class="ttcc-mini-label"><?php esc_html_e( 'Logo', 'ttcc-zmanim' ); ?></span>
				<img id="ttcc-logo-preview" class="ttcc-logo-preview" alt="" hidden />
				<button type="button" class="button button-small" id="ttcc-logo-choose"><?php esc_html_e( 'Choose…', 'ttcc-zmanim' ); ?></button>
				<button type="button" class="button button-small" id="ttcc-logo-remove" hidden><?php esc_html_e( 'Remove', 'ttcc-zmanim' ); ?></button>
			</span>
			<label><?php esc_html_e( 'Heading', 'ttcc-zmanim' ); ?>
				<select id="ttcc-heading-font">
					<option value="palatino"><?php esc_html_e( 'Palatino (serif)', 'ttcc-zmanim' ); ?></option>
					<option value="georgia"><?php esc_html_e( 'Georgia (serif)', 'ttcc-zmanim' ); ?></option>
					<option value="garamond"><?php esc_html_e( 'Garamond (serif)', 'ttcc-zmanim' ); ?></option>
					<option value="times"><?php esc_html_e( 'Times New Roman', 'ttcc-zmanim' ); ?></option>
					<option value="system"><?php esc_html_e( 'System sans', 'ttcc-zmanim' ); ?></option>
					<option value="helvetica"><?php esc_html_e( 'Helvetica / Arial', 'ttcc-zmanim' ); ?></option>
				</select>
			</label>
			<label><?php esc_html_e( 'Body', 'ttcc-zmanim' ); ?>
				<select id="ttcc-body-font">
					<option value="system"><?php esc_html_e( 'System sans', 'ttcc-zmanim' ); ?></option>
					<option value="helvetica"><?php esc_html_e( 'Helvetica / Arial', 'ttcc-zmanim' ); ?></option>
					<option value="palatino"><?php esc_html_e( 'Palatino (serif)', 'ttcc-zmanim' ); ?></option>
					<option value="georgia"><?php esc_html_e( 'Georgia (serif)', 'ttcc-zmanim' ); ?></option>
					<option value="garamond"><?php esc_html_e( 'Garamond (serif)', 'ttcc-zmanim' ); ?></option>
					<option value="times"><?php esc_html_e( 'Times New Roman', 'ttcc-zmanim' ); ?></option>
				</select>
			</label>
			<label title="<?php esc_attr_e( 'Where custom font names come from. Adobe uses the Web Project ID set in Settings.', 'ttcc-zmanim' ); ?>"><?php esc_html_e( 'Font source', 'ttcc-zmanim' ); ?>
				<select id="ttcc-font-source">
					<option value="google"><?php esc_html_e( 'Google Fonts', 'ttcc-zmanim' ); ?></option>
					<option value="adobe"><?php esc_html_e( 'Adobe Fonts', 'ttcc-zmanim' ); ?></option>
				</select>
			</label>
			<label title="<?php esc_attr_e( 'Optional custom family name. Overrides the Heading preset.', 'ttcc-zmanim' ); ?>"><?php esc_html_e( 'Heading (custom)', 'ttcc-zmanim' ); ?>
				<input type="text" id="ttcc-custom-heading" class="ttcc-gfont" placeholder="e.g. Playfair Display" />
			</label>
			<label title="<?php esc_attr_e( 'Optional custom family name for body text. Overrides the Body preset.', 'ttcc-zmanim' ); ?>"><?php esc_html_e( 'Body (custom)', 'ttcc-zmanim' ); ?>
				<input type="text" id="ttcc-custom-body" class="ttcc-gfont" placeholder="e.g. Inter" />
			</label>
			<label><?php esc_html_e( 'Size', 'ttcc-zmanim' ); ?>
				<input type="range" id="ttcc-base" min="11" max="24" step="1" />
			</label>
			<label class="ttcc-color"><?php esc_html_e( 'Text', 'ttcc-zmanim' ); ?>
				<input type="color" id="ttcc-text-color" />
			</label>
			<label class="ttcc-color"><?php esc_html_e( 'Note box', 'ttcc-zmanim' ); ?>
				<input type="color" id="ttcc-callout-bg" />
			</label>
			<label class="ttcc-color"><?php esc_html_e( 'Note text', 'ttcc-zmanim' ); ?>
				<input type="color" id="ttcc-callout-text" />
			</label>
		</div>
	</div>

	<div class="ttcc-toolbar ttcc-exports">
		<strong><?php esc_html_e( 'Export:', 'ttcc-zmanim' ); ?></strong>
		<button type="button" class="button" data-export="pdf"><?php esc_html_e( 'PDF', 'ttcc-zmanim' ); ?></button>
		<button type="button" class="button" data-export="png" data-variant="portrait"><?php esc_html_e( 'PNG (portrait)', 'ttcc-zmanim' ); ?></button>
		<button type="button" class="button" data-export="docx"><?php esc_html_e( 'Word (.docx)', 'ttcc-zmanim' ); ?></button>
		<button type="button" class="button" id="ttcc-whatsapp"><?php esc_html_e( 'WhatsApp message', 'ttcc-zmanim' ); ?></button>
		<span class="ttcc-engine-version" id="ttcc-engine-version"></span>
	</div>

	<div class="ttcc-wa" id="ttcc-wa" hidden>
		<div class="ttcc-wa-head">
			<strong><?php esc_html_e( 'WhatsApp broadcast', 'ttcc-zmanim' ); ?></strong>
			<button type="button" class="button button-small" id="ttcc-wa-copy"><?php esc_html_e( 'Copy', 'ttcc-zmanim' ); ?></button>
			<button type="button" class="button button-small" id="ttcc-wa-close"><?php esc_html_e( 'Close', 'ttcc-zmanim' ); ?></button>
			<span class="ttcc-wa-status" id="ttcc-wa-status" role="status" aria-live="polite"></span>
		</div>
		<textarea id="ttcc-wa-text" class="ttcc-wa-text" rows="16" readonly></textarea>
		<p class="description"><?php esc_html_e( 'Essential minyan times only. Paste into WhatsApp — the *asterisks* become bold.', 'ttcc-zmanim' ); ?></p>
	</div>

	<div class="ttcc-split" id="ttcc-split">
		<div class="ttcc-editor" id="ttcc-editor">
			<p class="ttcc-hint"><?php esc_html_e( 'Pick a week and press Generate to start.', 'ttcc-zmanim' ); ?></p>
		</div>
		<div class="ttcc-preview-wrap" id="ttcc-preview-wrap">
			<div class="ttcc-preview-bar">
				<span class="ttcc-preview-note" id="ttcc-preview-note"></span>
				<span class="ttcc-spacer"></span>
				<label class="ttcc-zoom-label"><?php esc_html_e( 'Zoom', 'ttcc-zmanim' ); ?>
					<input type="range" id="ttcc-zoom" min="40" max="200" step="5" value="100" />
				</label>
				<span class="ttcc-zoom-val" id="ttcc-zoom-val">100%</span>
				<button type="button" class="button button-small" id="ttcc-zoom-fit"><?php esc_html_e( 'Fit width', 'ttcc-zmanim' ); ?></button>
			</div>
			<div class="ttcc-preview-frame" id="ttcc-preview-frame">
				<iframe id="ttcc-preview" class="ttcc-preview" title="<?php esc_attr_e( 'Live sheet preview', 'ttcc-zmanim' ); ?>"></iframe>
			</div>
		</div>
	</div>
</div>
<?php
