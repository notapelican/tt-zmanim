/**
 * TTCC Timesheets dashboard editor.
 *
 * Block-level editor over a live HTML preview. The engine (via the sheet
 * service) computes every time; this UI only records overrides keyed by
 * rule_id (edit / suppress / add) and block-level note edits, then asks the
 * service to re-render. It never computes or re-rounds a time itself.
 *
 * Design notes:
 *  - Time inputs update overrides + refresh only the preview iframe (debounced),
 *    so typing never loses focus. Discrete actions (generate/revert/suppress/
 *    add/note) do a full rebuild.
 *  - "Original" (calculated) notes are captured with an empty note-override set
 *    so the editor can offer per-note remove + free-text add.
 */
( function () {
	'use strict';
	var cfg = window.TTCC || {};
	var app = document.getElementById( 'ttcc-app' );
	if ( ! app ) {
		return;
	}

	var state = {
		sheetId: parseInt( app.dataset.sheetId || '0', 10 ),
		start: '',
		end: '',
		title: '',
		status: 'draft',
		overrides: { lines: {}, notes: {} },
		originalNotes: {}, // blockKey -> [strings]
		doc: null,
		serviceOk: true
	};

	function $( id ) { return document.getElementById( id ); }
	function el( tag, cls, text ) {
		var n = document.createElement( tag );
		if ( cls ) { n.className = cls; }
		if ( undefined !== text && null !== text ) { n.textContent = text; }
		return n;
	}

	// --- API --------------------------------------------------------------
	function api( path, method, body ) {
		return fetch( cfg.restUrl + path, {
			method: method,
			headers: { 'Content-Type': 'application/json', 'X-WP-Nonce': cfg.nonce },
			body: body ? JSON.stringify( body ) : undefined
		} ).then( function ( res ) {
			return res.json().catch( function () { return null; } ).then( function ( data ) {
				if ( ! res.ok ) {
					var msg = ( data && ( data.message || data.detail ) ) || ( 'HTTP ' + res.status );
					var err = new Error( msg );
					err.status = res.status;
					throw err;
				}
				return data;
			} );
		} );
	}

	// --- health -----------------------------------------------------------
	function setHealth( ok, h ) {
		state.serviceOk = ok;
		var e = $( 'ttcc-health' );
		if ( ok ) {
			e.className = 'ttcc-health ok';
			e.textContent = 'Sheet service online — engine ' + ( h.engine_version || '' ) +
				( h.chromium ? ' · exports ready' : ' · Chromium missing (PDF/PNG will fail)' );
		} else {
			e.className = 'ttcc-health down';
			e.textContent = ( cfg.i18n && cfg.i18n.offline ) || ( 'Sheet service offline: ' + ( h && h.error || '' ) );
		}
		var dis = ! ok;
		[ 'ttcc-generate' ].forEach( function ( id ) { if ( $( id ) ) { $( id ).disabled = dis; } } );
		document.querySelectorAll( '[data-export]' ).forEach( function ( b ) { b.disabled = dis; } );
	}
	function pollHealth() {
		api( '/health', 'GET' ).then( function ( h ) { setHealth( !! h.ok, h ); } )
			.catch( function ( e ) { setHealth( false, { error: e.message } ); } );
	}

	// --- dates ------------------------------------------------------------
	function pad( n ) { return ( n < 10 ? '0' : '' ) + n; }
	function isoOf( d ) { return d.getFullYear() + '-' + pad( d.getMonth() + 1 ) + '-' + pad( d.getDate() ); }
	function currentSunday() {
		var d = new Date();
		d.setDate( d.getDate() - d.getDay() );
		return isoOf( d );
	}
	function addDays( iso, n ) {
		var d = new Date( iso + 'T00:00:00' );
		d.setDate( d.getDate() + n );
		return isoOf( d );
	}

	// --- preview ----------------------------------------------------------
	var previewTimer = null;
	function schedulePreview() {
		clearTimeout( previewTimer );
		previewTimer = setTimeout( function () { refresh( false ); }, 350 );
	}

	function injectPageGuides( html ) {
		// Approximate A4 printable-page height (273mm content ≈ 1032px @96dpi):
		// a visual "will it fit" guide, not exact Chromium pagination.
		var css = '<style id="ttcc-guides">body{background-image:repeating-linear-gradient(' +
			'to bottom,transparent 0,transparent 1031px,rgba(210,50,50,.5) 1031px,' +
			'rgba(210,50,50,.5) 1033px);background-attachment:local;}</style>';
		var i = html.toLowerCase().indexOf( '</head>' );
		return i < 0 ? css + html : html.slice( 0, i ) + css + html.slice( i );
	}

	function renderPreviewHtml( html ) {
		var iframe = $( 'ttcc-preview' );
		iframe.srcdoc = ( $( 'ttcc-pageguides' ).checked ) ? injectPageGuides( html ) : html;
	}

	/**
	 * @param {boolean} rebuildEditor  full editor rebuild (discrete actions) vs
	 *                                  iframe-only (during typing).
	 */
	function refresh( rebuildEditor ) {
		if ( ! state.start || ! state.end ) { return; }
		var note = $( 'ttcc-preview-note' );
		note.textContent = '…';
		api( '/preview', 'POST', { start: state.start, end: state.end, overrides: state.overrides } )
			.then( function ( data ) {
				state.doc = data.doc;
				$( 'ttcc-engine-version' ).textContent = data.engine_version ? ( 'engine ' + data.engine_version ) : '';
				renderPreviewHtml( data.html );
				if ( rebuildEditor ) { buildEditor( data.doc ); }
				note.textContent = '';
			} )
			.catch( function ( e ) {
				note.textContent = 'Preview unavailable: ' + e.message;
				if ( 503 === e.status ) { setHealth( false, { error: e.message } ); }
			} );
	}

	// Capture calculated notes (empty note-overrides) so remove/add can work.
	function captureOriginalNotes() {
		return api( '/preview', 'POST', { start: state.start, end: state.end, overrides: { lines: state.overrides.lines, notes: {} } } )
			.then( function ( data ) {
				state.originalNotes = {};
				( data.doc.blocks || [] ).forEach( function ( b ) {
					state.originalNotes[ blockKey( b ) ] = ( b.notes || [] ).slice();
				} );
			} ).catch( function () { /* leave originals as-is on failure */ } );
	}

	// --- editor -----------------------------------------------------------
	function blockKey( b ) {
		return ( 'day' === b.type ) ? ( 'day:' + ( b.date || '' ) ) : ( 'week:' + ( b.civil_start || '' ) );
	}

	function crossesBound( timeHHMM, bound ) {
		if ( ! bound || ! bound.time ) { return ''; }
		if ( 'not_before' === bound.direction && timeHHMM < bound.time ) {
			return 'earlier than ' + bound.zman + ' (' + bound.time + ')';
		}
		if ( 'not_after' === bound.direction && timeHHMM > bound.time ) {
			return 'later than ' + bound.zman + ' (' + bound.time + ')';
		}
		return '';
	}

	function lineRow( entry ) {
		var rid = entry.rule_id;
		var ov = state.overrides.lines[ rid ] || {};
		var row = el( 'div', 'ttcc-line' + ( ov.suppress ? ' suppressed' : '' ) );

		var lbl = el( 'div', 'lbl' );
		lbl.appendChild( document.createTextNode( entry.label ) );
		if ( entry.day_spec ) {
			var ds = el( 'span', 'dayspec', ' ' + entry.day_spec );
			lbl.appendChild( ds );
		}
		var badge = el( 'span', 'badge ' + ( entry.source || '' ), entry.source || '' );
		lbl.appendChild( badge );
		row.appendChild( lbl );

		var timeInput = el( 'input', 'time' );
		timeInput.type = 'time';
		timeInput.value = entry.time || '';
		timeInput.disabled = ( 'zman' === entry.kind ); // astronomical times are not editable
		row.appendChild( timeInput );

		var acts = el( 'div', 'acts' );
		var warn = el( 'div', 'ttcc-warn' );

		function showWarn() {
			warn.textContent = '';
			var msg = crossesBound( timeInput.value, entry.bound );
			if ( msg ) { warn.textContent = '⚠ ' + msg + ' — allowed, but check.'; }
		}

		timeInput.addEventListener( 'input', function () {
			state.overrides.lines[ rid ] = Object.assign( {}, state.overrides.lines[ rid ], { time: timeInput.value } );
			delete state.overrides.lines[ rid ].suppress;
			badge.textContent = 'override';
			badge.className = 'badge override';
			showWarn();
			schedulePreview();
		} );

		if ( 'zman' !== entry.kind ) {
			var supBtn = el( 'button', 'button button-small', ov.suppress ? 'Restore' : 'Remove' );
			supBtn.addEventListener( 'click', function () {
				var cur = state.overrides.lines[ rid ] || {};
				if ( cur.suppress ) { delete state.overrides.lines[ rid ]; }
				else { state.overrides.lines[ rid ] = { suppress: true }; }
				refresh( true );
			} );
			acts.appendChild( supBtn );
		}

		if ( state.overrides.lines[ rid ] && ( state.overrides.lines[ rid ].time || state.overrides.lines[ rid ].suppress ) && 0 !== rid.indexOf( 'add:' ) ) {
			var revBtn = el( 'button', 'button button-small', 'Revert' );
			revBtn.title = 'Revert to the calculated value';
			revBtn.addEventListener( 'click', function () {
				delete state.overrides.lines[ rid ];
				refresh( true );
			} );
			acts.appendChild( revBtn );
		}

		row.appendChild( acts );
		row.appendChild( warn );
		showWarn();
		return row;
	}

	function notesEditor( block ) {
		var key = blockKey( block );
		var wrap = el( 'div', 'ttcc-notes' );
		wrap.appendChild( el( 'div', 'ttcc-section-head', 'Notes' ) );

		var edit = state.overrides.notes[ key ] || { removed: [], added: [] };
		var originals = state.originalNotes[ key ] || ( block.notes || [] );

		originals.forEach( function ( text, idx ) {
			var line = el( 'div', 'note' );
			var cb = el( 'input' );
			cb.type = 'checkbox';
			cb.checked = ( -1 === ( edit.removed || [] ).indexOf( idx ) );
			cb.addEventListener( 'change', function () {
				var e = state.overrides.notes[ key ] || { removed: [], added: [] };
				e.removed = e.removed || [];
				var at = e.removed.indexOf( idx );
				if ( cb.checked && at > -1 ) { e.removed.splice( at, 1 ); }
				if ( ! cb.checked && at === -1 ) { e.removed.push( idx ); }
				state.overrides.notes[ key ] = e;
				schedulePreview();
			} );
			line.appendChild( cb );
			line.appendChild( el( 'span', '', text ) );
			wrap.appendChild( line );
		} );

		( edit.added || [] ).forEach( function ( text, i ) {
			var line = el( 'div', 'note' );
			var ta = el( 'textarea' );
			ta.rows = 2;
			ta.value = text;
			ta.addEventListener( 'input', function () {
				state.overrides.notes[ key ].added[ i ] = ta.value;
				schedulePreview();
			} );
			var del = el( 'button', 'button button-small', '×' );
			del.addEventListener( 'click', function () {
				state.overrides.notes[ key ].added.splice( i, 1 );
				refresh( true );
			} );
			line.appendChild( ta );
			line.appendChild( del );
			wrap.appendChild( line );
		} );

		var add = el( 'button', 'button button-small ttcc-add-note', '+ Add note' );
		add.addEventListener( 'click', function () {
			var e = state.overrides.notes[ key ] || { removed: [], added: [] };
			e.added = e.added || [];
			e.added.push( '' );
			state.overrides.notes[ key ] = e;
			refresh( true );
		} );
		wrap.appendChild( add );
		return wrap;
	}

	function addLineButton( block ) {
		var btn = el( 'button', 'button button-small ttcc-add-line', '+ Add line' );
		btn.addEventListener( 'click', function () {
			var label = window.prompt( 'Line label (e.g. "Special shiur")' );
			if ( ! label ) { return; }
			var time = window.prompt( 'Time (HH:MM, 24-hour)', '19:00' ) || '19:00';
			var id = 'add:' + Date.now().toString( 36 );
			state.overrides.lines[ id ] = {
				rule_id: id, section: null, label: label, kind: 'minyan',
				day_spec: null, date: block.date || null, time: time,
				qualifier: null, source: 'manual'
			};
			refresh( true );
		} );
		return btn;
	}

	function buildEditor( doc ) {
		var root = $( 'ttcc-editor' );
		root.innerHTML = '';
		if ( ! doc || ! doc.blocks || ! doc.blocks.length ) {
			root.appendChild( el( 'p', 'ttcc-hint', 'No blocks for this range.' ) );
			return;
		}
		doc.blocks.forEach( function ( block ) {
			var b = el( 'div', 'ttcc-block' );
			b.appendChild( el( 'h3', '', block.title || ( block.weekday ? ( block.weekday + ' ' + ( block.hebrew_date || '' ) ) : 'Block' ) ) );

			var curSection = '__none__';
			( block.entries || [] ).forEach( function ( entry ) {
				var sec = entry.section || '';
				if ( sec !== curSection ) {
					curSection = sec;
					if ( sec ) { b.appendChild( el( 'div', 'ttcc-section-head', sec ) ); }
				}
				b.appendChild( lineRow( entry ) );
			} );

			b.appendChild( addLineButton( block ) );
			b.appendChild( notesEditor( block ) );
			root.appendChild( b );
		} );
	}

	// --- actions ----------------------------------------------------------
	function doGenerate() {
		state.start = $( 'ttcc-start' ).value;
		state.end = $( 'ttcc-end' ).value;
		state.overrides = { lines: {}, notes: {} };
		if ( ! state.start || ! state.end ) { window.alert( 'Pick a start and end date.' ); return; }
		captureOriginalNotes().then( function () { refresh( true ); } );
	}

	function doSave() {
		var payload = {
			id: state.sheetId,
			title: $( 'ttcc-title' ).value,
			start: state.start,
			end: state.end,
			status: $( 'ttcc-status' ).value,
			overrides: state.overrides
		};
		api( '/timesheets', 'POST', payload ).then( function ( sheet ) {
			state.sheetId = sheet.id;
			app.dataset.sheetId = sheet.id;
			if ( window.history && window.history.replaceState ) {
				var u = new URL( window.location.href );
				u.searchParams.set( 'sheet', sheet.id );
				window.history.replaceState( {}, '', u.toString() );
			}
			$( 'ttcc-preview-note' ).textContent = 'Saved.';
		} ).catch( function ( e ) {
			$( 'ttcc-preview-note' ).textContent = 'Save failed: ' + e.message;
		} );
	}

	function doExport( kind, variant ) {
		var params = new URLSearchParams();
		params.set( 'action', 'ttcc_export' );
		params.set( 'kind', kind );
		if ( variant ) { params.set( 'variant', variant ); }
		params.set( '_wpnonce', cfg.exportNonce );
		if ( state.sheetId ) {
			params.set( 'sheet', String( state.sheetId ) );
		} else {
			params.set( 'start', state.start );
			params.set( 'end', state.end );
			params.set( 'overrides', JSON.stringify( state.overrides ) );
		}
		window.location.href = cfg.ajaxUrl + '?' + params.toString();
	}

	function loadSheet( id ) {
		api( '/timesheets/' + id, 'GET' ).then( function ( sheet ) {
			state.start = sheet.start_date;
			state.end = sheet.end_date;
			state.status = sheet.status;
			state.overrides = ( sheet.overrides && sheet.overrides.lines ) ? sheet.overrides : { lines: {}, notes: {} };
			$( 'ttcc-start' ).value = state.start;
			$( 'ttcc-end' ).value = state.end;
			$( 'ttcc-title' ).value = sheet.title || '';
			$( 'ttcc-status' ).value = state.status;
			captureOriginalNotes().then( function () { refresh( true ); } );
		} ).catch( function ( e ) {
			$( 'ttcc-preview-note' ).textContent = 'Load failed: ' + e.message;
		} );
	}

	// --- wire up ----------------------------------------------------------
	$( 'ttcc-generate' ).addEventListener( 'click', doGenerate );
	$( 'ttcc-save' ).addEventListener( 'click', doSave );
	$( 'ttcc-pageguides' ).addEventListener( 'change', function () {
		if ( state.doc ) { refresh( false ); }
	} );
	document.querySelectorAll( '[data-export]' ).forEach( function ( b ) {
		b.addEventListener( 'click', function () { doExport( b.dataset.export, b.dataset.variant ); } );
	} );

	// initial dates
	var sun = currentSunday();
	$( 'ttcc-start' ).value = sun;
	$( 'ttcc-end' ).value = addDays( sun, 6 );

	pollHealth();
	setInterval( pollHealth, 30000 );

	if ( state.sheetId ) { loadSheet( state.sheetId ); }
} )();
