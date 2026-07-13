<?php
/**
 * Archive view — list of stored timesheets with regenerate/edit/export links.
 *
 * @package TTCC_Zmanim
 * @var array $sheets
 */

defined( 'ABSPATH' ) || exit;

$dash = admin_url( 'admin.php?page=' . TTCC_Zmanim_Admin::MENU );
$ajax = admin_url( 'admin-ajax.php' );
$nonce = wp_create_nonce( 'ttcc_export' );
?>
<div class="wrap">
	<h1><?php esc_html_e( 'Timesheet archive', 'ttcc-zmanim' ); ?></h1>
	<?php if ( empty( $sheets ) ) : ?>
		<p><?php esc_html_e( 'No saved timesheets yet.', 'ttcc-zmanim' ); ?>
			<a href="<?php echo esc_url( $dash ); ?>"><?php esc_html_e( 'Create one', 'ttcc-zmanim' ); ?></a>.</p>
	<?php else : ?>
		<table class="wp-list-table widefat fixed striped">
			<thead>
				<tr>
					<th><?php esc_html_e( 'Title', 'ttcc-zmanim' ); ?></th>
					<th><?php esc_html_e( 'Range', 'ttcc-zmanim' ); ?></th>
					<th><?php esc_html_e( 'Status', 'ttcc-zmanim' ); ?></th>
					<th><?php esc_html_e( 'Engine', 'ttcc-zmanim' ); ?></th>
					<th><?php esc_html_e( 'Updated', 'ttcc-zmanim' ); ?></th>
					<th><?php esc_html_e( 'Actions', 'ttcc-zmanim' ); ?></th>
				</tr>
			</thead>
			<tbody>
				<?php foreach ( $sheets as $s ) : ?>
					<?php
					$edit_url = add_query_arg( 'sheet', (int) $s['id'], $dash );
					$pdf_url  = add_query_arg(
						array( 'action' => 'ttcc_export', 'kind' => 'pdf', 'sheet' => (int) $s['id'], '_wpnonce' => $nonce ),
						$ajax
					);
					?>
					<tr>
						<td><a href="<?php echo esc_url( $edit_url ); ?>"><?php echo esc_html( $s['title'] ? $s['title'] : __( '(untitled)', 'ttcc-zmanim' ) ); ?></a></td>
						<td><?php echo esc_html( $s['start_date'] . ' → ' . $s['end_date'] ); ?></td>
						<td><?php echo esc_html( $s['status'] ); ?></td>
						<td><code style="font-size:11px;"><?php echo esc_html( $s['engine_version'] ); ?></code></td>
						<td><?php echo esc_html( $s['updated_at'] ); ?></td>
						<td>
							<a class="button button-small" href="<?php echo esc_url( $edit_url ); ?>"><?php esc_html_e( 'Edit / regenerate', 'ttcc-zmanim' ); ?></a>
							<a class="button button-small" href="<?php echo esc_url( $pdf_url ); ?>"><?php esc_html_e( 'PDF', 'ttcc-zmanim' ); ?></a>
						</td>
					</tr>
				<?php endforeach; ?>
			</tbody>
		</table>
	<?php endif; ?>
</div>
<?php
