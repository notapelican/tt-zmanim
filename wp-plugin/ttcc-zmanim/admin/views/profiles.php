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

	<h2><?php esc_html_e( 'Profiles (JSON)', 'ttcc-zmanim' ); ?></h2>
	<textarea id="ttcc-profiles-json" class="large-text code" rows="22" spellcheck="false"></textarea>

	<h2><?php esc_html_e( 'Note templates (JSON)', 'ttcc-zmanim' ); ?></h2>
	<textarea id="ttcc-notes-json" class="large-text code" rows="10" spellcheck="false"></textarea>
</div>
<?php
