/**
 * Schedule-profiles editor: load/save the active profile set as JSON, or reset
 * to the engine defaults (fetched from the service). The service's adapter
 * turns this JSON back into the engine's dataclasses.
 */
( function () {
	'use strict';
	var cfg = window.TTCC || {};
	if ( ! document.getElementById( 'ttcc-profiles-app' ) ) { return; }

	function $( id ) { return document.getElementById( id ); }
	function status( msg, down ) {
		var e = $( 'ttcc-profiles-status' );
		e.className = 'ttcc-health ' + ( down ? 'down' : 'ok' );
		e.textContent = msg;
	}

	function api( path, method, body ) {
		return fetch( cfg.restUrl + path, {
			method: method,
			headers: { 'Content-Type': 'application/json', 'X-WP-Nonce': cfg.nonce },
			body: body ? JSON.stringify( body ) : undefined
		} ).then( function ( res ) {
			return res.json().catch( function () { return null; } ).then( function ( data ) {
				if ( ! res.ok ) { throw new Error( ( data && ( data.message || data.detail ) ) || ( 'HTTP ' + res.status ) ); }
				return data;
			} );
		} );
	}

	function fill( data ) {
		$( 'ttcc-profiles-json' ).value = JSON.stringify( data.profiles || [], null, 2 );
		$( 'ttcc-notes-json' ).value = JSON.stringify( data.notes || [], null, 2 );
	}

	function load() {
		api( '/profiles', 'GET' ).then( function ( d ) { fill( d ); status( 'Loaded.' ); } )
			.catch( function ( e ) { status( 'Load failed: ' + e.message, true ); } );
	}

	$( 'ttcc-profiles-save' ).addEventListener( 'click', function () {
		var profiles, notes;
		try {
			profiles = JSON.parse( $( 'ttcc-profiles-json' ).value );
			notes = JSON.parse( $( 'ttcc-notes-json' ).value || '[]' );
		} catch ( err ) {
			status( 'Invalid JSON: ' + err.message, true );
			return;
		}
		api( '/profiles', 'POST', { profiles: profiles, notes: notes } )
			.then( function ( d ) { fill( d ); status( 'Saved.' ); } )
			.catch( function ( e ) { status( 'Save failed: ' + e.message, true ); } );
	} );

	$( 'ttcc-profiles-reset' ).addEventListener( 'click', function () {
		if ( ! window.confirm( 'Reset profiles and notes to the engine defaults?' ) ) { return; }
		api( '/profiles/reset', 'POST' ).then( function ( d ) { fill( d ); status( 'Reset to engine defaults.' ); } )
			.catch( function ( e ) { status( 'Reset failed: ' + e.message, true ); } );
	} );

	load();
} )();
