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

	/**
	 * Mirrors PUC's Vcs\Api::REQUIRE_RELEASE_ASSETS. Held as a literal so the
	 * namespaced class (whose version segment moves with the vendored library)
	 * need not be referenced; resolve_asset_preference() prefers the real
	 * constant when it can find it, so a value change upstream cannot go
	 * unnoticed.
	 */
	const REQUIRE_RELEASE_ASSETS = 2;

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
			// Install the attached plugin-only zip, and NOTHING else.
			//
			// The second argument matters more than it looks. PUC starts every
			// release off with downloadUrl = the release's zipball (the whole
			// monorepo) and only swaps in the asset once it finds one matching the
			// filter. Its default preference then tolerates not finding one and
			// installs that source zip — which unpacks engine/, service/ and
			// wp-plugin/ into wp-content/plugins/ttcc-zmanim/, leaving no
			// ttcc-zmanim.php at the top level. WordPress deactivates the plugin
			// as missing and it vanishes from the Plugins screen. (That is not
			// hypothetical: it happened on 0.6.7. The release-publish and
			// asset-upload are two API calls ~15s apart, so an update check
			// landing between them sees a release with no assets at all, and the
			// bad URL is then cached for hours.)
			//
			// Requiring the asset makes the failure harmless: no matching zip
			// means no update offered, which is a wait, not a broken site.
			$api->enableReleaseAssets( self::ASSET_RE, self::resolve_asset_preference() );
		}
	}

	/**
	 * PUC's REQUIRE_RELEASE_ASSETS preference, read from the library when the
	 * vendored class can be located so an upstream value change is picked up,
	 * and from our own mirror of it otherwise.
	 */
	private static function resolve_asset_preference() {
		foreach ( array( 'v5p6', 'v5p5', 'v5p4', 'v5' ) as $ver ) {
			$class = '\\YahnisElsts\\PluginUpdateChecker\\' . $ver . '\\Vcs\\Api';
			if ( class_exists( $class ) && defined( $class . '::REQUIRE_RELEASE_ASSETS' ) ) {
				return constant( $class . '::REQUIRE_RELEASE_ASSETS' );
			}
		}
		return self::REQUIRE_RELEASE_ASSETS;
	}
}
