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
		populateRecProfiles( data.profiles || [] );
	}

	// Populate the "recurring minyan" schedule dropdown from the loaded profiles.
	function populateRecProfiles( profiles ) {
		var sel = $( 'ttcc-rec-profile' );
		if ( ! sel ) { return; }
		sel.innerHTML = '';
		profiles.forEach( function ( p ) {
			var o = document.createElement( 'option' );
			o.value = p.id;
			o.textContent = p.name || p.id;
			sel.appendChild( o );
		} );
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

	// Add-recurring-minyan form: append a fixed-time rule to the chosen profile,
	// write it into the JSON, and save immediately.
	if ( $( 'ttcc-rec-add' ) ) {
		$( 'ttcc-rec-add' ).addEventListener( 'click', function () {
			var label = $( 'ttcc-rec-label' ).value.trim();
			var time = $( 'ttcc-rec-time' ).value;
			if ( ! label ) { status( 'Enter a label for the minyan.', true ); return; }
			if ( ! time ) { status( 'Enter a time.', true ); return; }
			var profiles;
			try { profiles = JSON.parse( $( 'ttcc-profiles-json' ).value ); }
			catch ( e ) { status( 'Profiles JSON is invalid; fix it before adding.', true ); return; }
			var pid = $( 'ttcc-rec-profile' ).value;
			var target = profiles.filter( function ( p ) { return p.id === pid; } )[ 0 ];
			if ( ! target ) { status( 'Pick a schedule.', true ); return; }
			var days = $( 'ttcc-rec-days' ).value.trim();
			target.rules = target.rules || [];
			target.rules.push( {
				id: 'extra_' + Date.now().toString( 36 ),
				section: $( 'ttcc-rec-section' ).value,
				label: label,
				timing: { type: 'fixed', time: time },
				day_spec: days || null,
				qualifier: null, bound: null, when: null, kind: 'minyan'
			} );
			var notes;
			try { notes = JSON.parse( $( 'ttcc-notes-json' ).value || '[]' ); }
			catch ( e ) { notes = []; }
			api( '/profiles', 'POST', { profiles: profiles, notes: notes } )
				.then( function ( d ) {
					fill( d );
					$( 'ttcc-rec-label' ).value = ''; $( 'ttcc-rec-time' ).value = ''; $( 'ttcc-rec-days' ).value = '';
					status( 'Added “' + label + '” to the schedule and saved.' );
				} )
				.catch( function ( e ) { status( 'Add failed: ' + e.message, true ); } );
		} );
	}

	load();
} )();
