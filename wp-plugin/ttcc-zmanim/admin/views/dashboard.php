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

	<?php
	// Shared preset-font options; header/subheader selects add a "Default" row.
	$ttcc_fonts = array(
		'palatino'  => __( 'Palatino (serif)', 'ttcc-zmanim' ),
		'georgia'   => __( 'Georgia (serif)', 'ttcc-zmanim' ),
		'garamond'  => __( 'Garamond (serif)', 'ttcc-zmanim' ),
		'times'     => __( 'Times New Roman', 'ttcc-zmanim' ),
		'system'    => __( 'System sans', 'ttcc-zmanim' ),
		'helvetica' => __( 'Helvetica / Arial', 'ttcc-zmanim' ),
	);
	$ttcc_aligns = array(
		''       => __( 'Default', 'ttcc-zmanim' ),
		'left'   => __( 'Left', 'ttcc-zmanim' ),
		'center' => __( 'Centre', 'ttcc-zmanim' ),
		'right'  => __( 'Right', 'ttcc-zmanim' ),
	);
	?>
	<div class="ttcc-toolbar ttcc-design-bar">
		<label><?php esc_html_e( 'Layout', 'ttcc-zmanim' ); ?>
			<select id="ttcc-layout">
				<option value="classic"><?php esc_html_e( 'Classic', 'ttcc-zmanim' ); ?></option>
				<option value="modern"><?php esc_html_e( 'Modern', 'ttcc-zmanim' ); ?></option>
			</select>
		</label>
		<div id="ttcc-design" class="ttcc-design">
			<span class="ttcc-design-group ttcc-preset-group">
				<span class="ttcc-mini-label"><?php esc_html_e( 'Preset', 'ttcc-zmanim' ); ?></span>
				<select id="ttcc-preset" title="<?php esc_attr_e( 'Saved styling presets', 'ttcc-zmanim' ); ?>">
					<option value=""><?php esc_html_e( '— none —', 'ttcc-zmanim' ); ?></option>
				</select>
				<button type="button" class="button button-small" id="ttcc-preset-apply"><?php esc_html_e( 'Apply', 'ttcc-zmanim' ); ?></button>
				<button type="button" class="button button-small" id="ttcc-preset-save"><?php esc_html_e( 'Save current…', 'ttcc-zmanim' ); ?></button>
				<button type="button" class="button button-small" id="ttcc-preset-delete"><?php esc_html_e( 'Delete', 'ttcc-zmanim' ); ?></button>
				<label title="<?php esc_attr_e( 'Use this preset as the starting design for new sheets', 'ttcc-zmanim' ); ?>"><input type="checkbox" id="ttcc-preset-default" /> <?php esc_html_e( 'Default', 'ttcc-zmanim' ); ?></label>
			</span>
			<?php foreach ( array( 'header' => __( 'Header (name line)', 'ttcc-zmanim' ), 'subheader' => __( 'Subheader (location line)', 'ttcc-zmanim' ) ) as $t => $ttl ) : ?>
			<span class="ttcc-design-group">
				<span class="ttcc-mini-label"><?php echo esc_html( $ttl ); ?></span>
				<select id="ttcc-<?php echo esc_attr( $t ); ?>-font" title="<?php esc_attr_e( 'Font', 'ttcc-zmanim' ); ?>">
					<option value=""><?php esc_html_e( 'Default font', 'ttcc-zmanim' ); ?></option>
					<?php foreach ( $ttcc_fonts as $k => $label ) : ?>
						<option value="<?php echo esc_attr( $k ); ?>"><?php echo esc_html( $label ); ?></option>
					<?php endforeach; ?>
				</select>
				<input type="number" id="ttcc-<?php echo esc_attr( $t ); ?>-size" class="ttcc-size" min="8" max="48" step="1"
					placeholder="<?php esc_attr_e( 'auto', 'ttcc-zmanim' ); ?>" title="<?php esc_attr_e( 'Size (px, blank = default)', 'ttcc-zmanim' ); ?>" />
				<select id="ttcc-<?php echo esc_attr( $t ); ?>-align" title="<?php esc_attr_e( 'Justification', 'ttcc-zmanim' ); ?>">
					<?php foreach ( $ttcc_aligns as $k => $label ) : ?>
						<option value="<?php echo esc_attr( $k ); ?>"><?php echo esc_html( $label ); ?></option>
					<?php endforeach; ?>
				</select>
			</span>
			<?php endforeach; ?>
			<span class="ttcc-design-group">
				<span class="ttcc-mini-label"><?php esc_html_e( 'Content', 'ttcc-zmanim' ); ?></span>
				<select id="ttcc-body-font" title="<?php esc_attr_e( 'Content font', 'ttcc-zmanim' ); ?>">
					<option value=""><?php esc_html_e( 'Default font', 'ttcc-zmanim' ); ?></option>
					<?php foreach ( $ttcc_fonts as $k => $label ) : ?>
						<option value="<?php echo esc_attr( $k ); ?>"><?php echo esc_html( $label ); ?></option>
					<?php endforeach; ?>
				</select>
				<label class="ttcc-inline"><?php esc_html_e( 'Size', 'ttcc-zmanim' ); ?>
					<input type="range" id="ttcc-base" min="11" max="24" step="1" />
				</label>
			</span>
			<span class="ttcc-design-group ttcc-modern-only">
				<span class="ttcc-mini-label"><?php esc_html_e( 'Week headings', 'ttcc-zmanim' ); ?></span>
				<select id="ttcc-heading-font" title="<?php esc_attr_e( 'Week/section heading font (modern layout)', 'ttcc-zmanim' ); ?>">
					<?php foreach ( $ttcc_fonts as $k => $label ) : ?>
						<option value="<?php echo esc_attr( $k ); ?>"><?php echo esc_html( $label ); ?></option>
					<?php endforeach; ?>
				</select>
			</span>
			<span class="ttcc-design-group ttcc-modern-only ttcc-logo-field">
				<span class="ttcc-mini-label"><?php esc_html_e( 'Logo', 'ttcc-zmanim' ); ?></span>
				<img id="ttcc-logo-preview" class="ttcc-logo-preview" alt="" hidden />
				<button type="button" class="button button-small" id="ttcc-logo-choose"><?php esc_html_e( 'Choose…', 'ttcc-zmanim' ); ?></button>
				<button type="button" class="button button-small" id="ttcc-logo-remove" hidden><?php esc_html_e( 'Remove', 'ttcc-zmanim' ); ?></button>
				<label class="ttcc-inline"><?php esc_html_e( 'Size', 'ttcc-zmanim' ); ?>
					<input type="range" id="ttcc-logo-size" min="20" max="140" step="2" />
				</label>
			</span>
			<span class="ttcc-design-group ttcc-modern-only">
				<span class="ttcc-mini-label"><?php esc_html_e( 'Custom fonts', 'ttcc-zmanim' ); ?></span>
				<select id="ttcc-font-source" title="<?php esc_attr_e( 'Where custom font names come from. Adobe uses the Web Project ID set in Settings.', 'ttcc-zmanim' ); ?>">
					<option value="google"><?php esc_html_e( 'Google Fonts', 'ttcc-zmanim' ); ?></option>
					<option value="adobe"><?php esc_html_e( 'Adobe Fonts', 'ttcc-zmanim' ); ?></option>
				</select>
				<input type="text" id="ttcc-custom-heading" class="ttcc-gfont" placeholder="<?php esc_attr_e( 'Heading family, e.g. Playfair Display', 'ttcc-zmanim' ); ?>" />
				<input type="text" id="ttcc-custom-body" class="ttcc-gfont" placeholder="<?php esc_attr_e( 'Body family, e.g. Inter', 'ttcc-zmanim' ); ?>" />
			</span>
			<span class="ttcc-design-group ttcc-modern-only">
				<span class="ttcc-mini-label"><?php esc_html_e( 'Colors', 'ttcc-zmanim' ); ?></span>
				<label class="ttcc-color"><?php esc_html_e( 'Text', 'ttcc-zmanim' ); ?>
					<input type="color" id="ttcc-text-color" />
				</label>
				<label class="ttcc-color"><?php esc_html_e( 'Note box', 'ttcc-zmanim' ); ?>
					<input type="color" id="ttcc-callout-bg" />
				</label>
				<label class="ttcc-color"><?php esc_html_e( 'Note text', 'ttcc-zmanim' ); ?>
					<input type="color" id="ttcc-callout-text" />
				</label>
			</span>
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
