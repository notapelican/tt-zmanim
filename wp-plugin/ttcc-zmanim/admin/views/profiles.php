<?php
/**
 * Schedule-profiles view — a container the profiles JS drives. Profiles are
 * edited as structured JSON (seeded from the engine defaults); the adapter on
 * the service turns them back into the engine's dataclasses.
 *
 * @package TTCC_Zmanim
 */

defined( 'ABSPATH' ) || exit;
?>
<div class="wrap ttcc-profiles" id="ttcc-profiles-app">
	<h1><?php esc_html_e( 'Schedule profiles', 'ttcc-zmanim' ); ?></h1>
	<p class="description">
		<?php esc_html_e( 'Seasonal minyan sets and note templates used to generate sheets. Zman-anchored lines carry the halachic bound the dashboard warns against; times are always recomputed by the engine. Reset restores the engine defaults.', 'ttcc-zmanim' ); ?>
	</p>

	<div id="ttcc-profiles-status" class="ttcc-health" role="status" aria-live="polite"></div>

	<p>
		<button type="button" class="button button-primary" id="ttcc-profiles-save"><?php esc_html_e( 'Save profiles', 'ttcc-zmanim' ); ?></button>
		<button type="button" class="button" id="ttcc-profiles-reset"><?php esc_html_e( 'Reset to engine defaults', 'ttcc-zmanim' ); ?></button>
	</p>

	<h2><?php esc_html_e( 'Add a recurring minyan', 'ttcc-zmanim' ); ?></h2>
	<p class="description">
		<?php esc_html_e( 'Adds a fixed-time davening line that appears automatically on every sheet the chosen schedule covers. For a one-off line on a single sheet, use “+ Add line” on the dashboard instead.', 'ttcc-zmanim' ); ?>
	</p>
	<div class="ttcc-recurring-form">
		<label><?php esc_html_e( 'Schedule', 'ttcc-zmanim' ); ?>
			<select id="ttcc-rec-profile"></select>
		</label>
		<label><?php esc_html_e( 'Section', 'ttcc-zmanim' ); ?>
			<select id="ttcc-rec-section">
				<option value="weekday_davening"><?php esc_html_e( 'During the week', 'ttcc-zmanim' ); ?></option>
				<option value="erev_shabbos_davening"><?php esc_html_e( 'Erev Shabbos', 'ttcc-zmanim' ); ?></option>
				<option value="shabbos_day"><?php esc_html_e( 'Shabbos day / Motzaei', 'ttcc-zmanim' ); ?></option>
				<option value="erev_shabbos_early_minyan"><?php esc_html_e( 'Erev Shabbos early minyan', 'ttcc-zmanim' ); ?></option>
			</select>
		</label>
		<label><?php esc_html_e( 'Label', 'ttcc-zmanim' ); ?>
			<input type="text" id="ttcc-rec-label" placeholder="<?php esc_attr_e( 'e.g. Daf Yomi', 'ttcc-zmanim' ); ?>" />
		</label>
		<label><?php esc_html_e( 'Time', 'ttcc-zmanim' ); ?>
			<input type="time" id="ttcc-rec-time" />
		</label>
		<label><?php esc_html_e( 'Days (optional)', 'ttcc-zmanim' ); ?>
			<input type="text" id="ttcc-rec-days" placeholder="<?php esc_attr_e( 'e.g. Sun.–Thurs.', 'ttcc-zmanim' ); ?>" />
		</label>
		<button type="button" class="button" id="ttcc-rec-add"><?php esc_html_e( 'Add to schedule', 'ttcc-zmanim' ); ?></button>
	</div>

	<h2><?php esc_html_e( 'Profiles (JSON)', 'ttcc-zmanim' ); ?></h2>
	<p class="description"><?php esc_html_e( 'Advanced: the full schedule as JSON. The form above edits this for you; edit directly only if you know the format.', 'ttcc-zmanim' ); ?></p>
	<textarea id="ttcc-profiles-json" class="large-text code" rows="22" spellcheck="false"></textarea>

	<h2><?php esc_html_e( 'Note templates (JSON)', 'ttcc-zmanim' ); ?></h2>
	<textarea id="ttcc-notes-json" class="large-text code" rows="10" spellcheck="false"></textarea>
</div>
<?php
