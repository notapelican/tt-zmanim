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

	<div class="ttcc-toolbar ttcc-exports">
		<strong><?php esc_html_e( 'Export:', 'ttcc-zmanim' ); ?></strong>
		<button type="button" class="button" data-export="pdf"><?php esc_html_e( 'PDF', 'ttcc-zmanim' ); ?></button>
		<button type="button" class="button" data-export="png" data-variant="portrait"><?php esc_html_e( 'PNG (portrait)', 'ttcc-zmanim' ); ?></button>
		<button type="button" class="button" data-export="docx"><?php esc_html_e( 'Word (.docx)', 'ttcc-zmanim' ); ?></button>
		<span class="ttcc-engine-version" id="ttcc-engine-version"></span>
	</div>

	<div class="ttcc-split">
		<div class="ttcc-editor" id="ttcc-editor">
			<p class="ttcc-hint"><?php esc_html_e( 'Pick a week and press Generate to start.', 'ttcc-zmanim' ); ?></p>
		</div>
		<div class="ttcc-preview-wrap">
			<div class="ttcc-preview-note" id="ttcc-preview-note"></div>
			<iframe id="ttcc-preview" class="ttcc-preview" title="<?php esc_attr_e( 'Live sheet preview', 'ttcc-zmanim' ); ?>"></iframe>
		</div>
	</div>
</div>
<?php
