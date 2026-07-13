<?php
/**
 * Over-the-air plugin updates from the private GitHub repo.
 *
 * Uses the vendored Plugin Update Checker (YahnisElsts) in GitHub *release
 * assets* mode: each release tag (e.g. v0.2.0) carries a plugin-only
 * `ttcc-zmanim.zip` built by .github/workflows/release-plugin.yml. The library
 * compares the release tag to the installed version and, when newer, shows the
 * normal "update available" prompt in Plugins → Installed. The download is
 * authenticated with the GitHub token from Settings (never exposed to the
 * browser), which also lets it work for a private repo.
 *
 * Release-assets mode sidesteps the monorepo layout: the version comes from the
 * tag and the package is the attached zip, so the repo also holding engine/ and
 * service/ is irrelevant to the update.
 *
 * @package TTCC_Zmanim
 */

defined( 'ABSPATH' ) || exit;

class TTCC_Zmanim_Updater {

	const REPO      = 'https://github.com/notapelican/tt-zmanim/';
	const SLUG      = 'ttcc-zmanim';
	const ASSET_RE  = '/ttcc-zmanim\.zip$/i';

	public static function init() {
		$loader = TTCC_ZMANIM_DIR . 'plugin-update-checker/plugin-update-checker.php';
		if ( ! file_exists( $loader ) ) {
			return;
		}
		require_once $loader;

		$factory = '\\YahnisElsts\\PluginUpdateChecker\\v5\\PucFactory';
		if ( ! class_exists( $factory ) ) {
			return;
		}

		$checker = $factory::buildUpdateChecker( self::REPO, TTCC_ZMANIM_FILE, self::SLUG );

		$token = trim( (string) TTCC_Zmanim_Settings::get( 'github_token', '' ) );
		if ( '' !== $token ) {
			$checker->setAuthentication( $token );
		}

		$api = $checker->getVcsApi();
		if ( is_object( $api ) && method_exists( $api, 'enableReleaseAssets' ) ) {
			// Install the attached plugin-only zip, not the monorepo source.
			$api->enableReleaseAssets( self::ASSET_RE );
		}
	}
}
