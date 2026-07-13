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

	// Modern-layout design defaults (a global default set may arrive from
	// Settings via cfg.designDefaults; fall back to the renderer's own defaults).
	var DESIGN_DEFAULTS = ( cfg.designDefaults && 'object' === typeof cfg.designDefaults ) ? cfg.designDefaults : {};
	function defaultDesign() {
		return {
			logo:         DESIGN_DEFAULTS.logo || '',
			heading_font: DESIGN_DEFAULTS.heading_font || 'palatino',
			body_font:    DESIGN_DEFAULTS.body_font || 'system',
			font_source:  DESIGN_DEFAULTS.font_source || 'google',
			custom_heading: DESIGN_DEFAULTS.custom_heading || '',
			custom_body:  DESIGN_DEFAULTS.custom_body || '',
			base:         parseInt( DESIGN_DEFAULTS.base, 10 ) || 15,
			text_color:   DESIGN_DEFAULTS.text_color || '#1b1e28',
			callout_bg:   DESIGN_DEFAULTS.callout_bg || '#fbeef1',
			callout_text: DESIGN_DEFAULTS.callout_text || '#a3324b'
		};
	}
	function defaultOverrides() {
		return { lines: {}, notes: {}, template: DESIGN_DEFAULTS.template || 'classic', design: defaultDesign() };
	}

	var state = {
		sheetId: parseInt( app.dataset.sheetId || '0', 10 ),
		start: '',
		end: '',
		title: '',
		status: 'draft',
		overrides: defaultOverrides(),
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
		[ 'ttcc-generate', 'ttcc-whatsapp' ].forEach( function ( id ) { if ( $( id ) ) { $( id ).disabled = dis; } } );
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
	function daysBetween( a, b ) {
		return Math.round( ( new Date( b + 'T00:00:00' ) - new Date( a + 'T00:00:00' ) ) / 86400000 );
	}

	// --- multi-week range -------------------------------------------------
	// The engine already lays out multiple weeks (two-column stacked sheet)
	// for any range spanning >1 week; this UI just makes the range easy to set
	// and shows how many weeks it covers.
	function syncEndFromWeeks() {
		var sel = $( 'ttcc-weeks' ), start = $( 'ttcc-start' ).value;
		if ( ! sel || 'custom' === sel.value || ! start ) { return; }
		$( 'ttcc-end' ).value = addDays( start, parseInt( sel.value, 10 ) * 7 - 1 );
	}
	function setWeeksSelectFromDates() {
		var sel = $( 'ttcc-weeks' ), s = $( 'ttcc-start' ).value, e = $( 'ttcc-end' ).value;
		if ( ! sel || ! s || ! e ) { return; }
		var days = daysBetween( s, e ) + 1, wk = days / 7;
		sel.value = ( days > 0 && 0 === days % 7 && wk >= 1 && wk <= 4 ) ? String( wk ) : 'custom';
	}
	function weekTitle( b ) { return b.parsha || b.title || ''; }
	function updateRangeLabel( doc ) {
		var lbl = $( 'ttcc-range-label' );
		if ( ! lbl ) { return; }
		if ( doc && doc.blocks ) {
			var weeks = doc.blocks.filter( function ( b ) { return 'week' === b.type; } );
			if ( weeks.length ) {
				var n = weeks.length, first = weekTitle( weeks[ 0 ] ), last = weekTitle( weeks[ n - 1 ] );
				var span = n + ( 1 === n ? ' week' : ' weeks' );
				var range = ( n > 1 && first && last ) ? ( ': ' + first + ' → ' + last )
					: ( first ? ( ': ' + first ) : '' );
				lbl.textContent = 'This sheet spans ' + span + range + '.';
				return;
			}
		}
		// provisional (before generating): estimate from the date range.
		var s = $( 'ttcc-start' ).value, e = $( 'ttcc-end' ).value;
		if ( s && e && daysBetween( s, e ) >= 0 ) {
			var est = Math.max( 1, Math.round( ( daysBetween( s, e ) + 1 ) / 7 ) );
			lbl.textContent = est + ( 1 === est ? ' week selected' : ' weeks selected' ) + ' — press Generate.';
		} else {
			lbl.textContent = '';
		}
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
				updateRangeLabel( data.doc );
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
		// New range clears line/note edits but keeps the chosen layout + design.
		state.overrides = { lines: {}, notes: {}, template: state.overrides.template, design: state.overrides.design };
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
			var ov = ( sheet.overrides && sheet.overrides.lines ) ? sheet.overrides : {};
			state.overrides = {
				lines: ov.lines || {}, notes: ov.notes || {},
				template: ov.template || 'classic',
				design: Object.assign( defaultDesign(), ov.design || {} )
			};
			$( 'ttcc-start' ).value = state.start;
			$( 'ttcc-end' ).value = state.end;
			$( 'ttcc-title' ).value = sheet.title || '';
			$( 'ttcc-status' ).value = state.status;
			setWeeksSelectFromDates();
			syncDesignUI();
			captureOriginalNotes().then( function () { refresh( true ); } );
		} ).catch( function ( e ) {
			$( 'ttcc-preview-note' ).textContent = 'Load failed: ' + e.message;
		} );
	}

	// --- WhatsApp broadcast -----------------------------------------------
	function doWhatsApp() {
		if ( ! state.start || ! state.end ) { window.alert( 'Pick a start and end date, then Generate.' ); return; }
		var panel = $( 'ttcc-wa' ), ta = $( 'ttcc-wa-text' ), st = $( 'ttcc-wa-status' );
		panel.hidden = false;
		st.textContent = '';
		ta.value = '…';
		api( '/whatsapp', 'POST', { start: state.start, end: state.end, overrides: state.overrides } )
			.then( function ( data ) { ta.value = data.text || ''; } )
			.catch( function ( e ) {
				ta.value = '';
				st.textContent = 'Failed: ' + e.message;
				if ( 503 === e.status ) { setHealth( false, { error: e.message } ); }
			} );
	}
	function copyWhatsApp() {
		var ta = $( 'ttcc-wa-text' ), st = $( 'ttcc-wa-status' );
		var done = function () { st.textContent = 'Copied!'; };
		if ( navigator.clipboard && navigator.clipboard.writeText ) {
			navigator.clipboard.writeText( ta.value ).then( done, function () { ta.select(); document.execCommand( 'copy' ); done(); } );
		} else {
			ta.select(); document.execCommand( 'copy' ); done();
		}
	}

	// --- design panel (modern layout) -------------------------------------
	function updateLogoPreview() {
		var img = $( 'ttcc-logo-preview' ), rm = $( 'ttcc-logo-remove' );
		var url = state.overrides.design.logo;
		if ( url ) { img.src = url; img.hidden = false; rm.hidden = false; }
		else { img.removeAttribute( 'src' ); img.hidden = true; rm.hidden = true; }
	}
	function syncDesignUI() {
		var d = state.overrides.design;
		$( 'ttcc-layout' ).value = state.overrides.template || 'classic';
		$( 'ttcc-design' ).hidden = ( 'modern' !== state.overrides.template );
		$( 'ttcc-heading-font' ).value = d.heading_font;
		$( 'ttcc-body-font' ).value = d.body_font;
		$( 'ttcc-font-source' ).value = d.font_source || 'google';
		$( 'ttcc-custom-heading' ).value = d.custom_heading || '';
		$( 'ttcc-custom-body' ).value = d.custom_body || '';
		$( 'ttcc-base' ).value = d.base;
		$( 'ttcc-text-color' ).value = d.text_color;
		$( 'ttcc-callout-bg' ).value = d.callout_bg;
		$( 'ttcc-callout-text' ).value = d.callout_text;
		updateLogoPreview();
	}
	var mediaFrame = null;
	function chooseLogo() {
		if ( window.wp && window.wp.media ) {
			if ( ! mediaFrame ) {
				mediaFrame = window.wp.media( { title: 'Select logo', button: { text: 'Use this logo' }, multiple: false, library: { type: 'image' } } );
				mediaFrame.on( 'select', function () {
					var att = mediaFrame.state().get( 'selection' ).first().toJSON();
					state.overrides.design.logo = att.url;
					updateLogoPreview();
					schedulePreview();
				} );
			}
			mediaFrame.open();
			return;
		}
		var url = window.prompt( 'Logo image URL' );
		if ( url ) { state.overrides.design.logo = url; updateLogoPreview(); schedulePreview(); }
	}
	function wireDesign() {
		$( 'ttcc-layout' ).addEventListener( 'change', function () {
			state.overrides.template = $( 'ttcc-layout' ).value;
			$( 'ttcc-design' ).hidden = ( 'modern' !== state.overrides.template );
			if ( state.doc ) { refresh( false ); }
		} );
		[ [ 'ttcc-heading-font', 'heading_font' ], [ 'ttcc-body-font', 'body_font' ],
		  [ 'ttcc-font-source', 'font_source' ], [ 'ttcc-custom-heading', 'custom_heading' ], [ 'ttcc-custom-body', 'custom_body' ],
		  [ 'ttcc-base', 'base' ], [ 'ttcc-text-color', 'text_color' ],
		  [ 'ttcc-callout-bg', 'callout_bg' ], [ 'ttcc-callout-text', 'callout_text' ] ]
		.forEach( function ( pair ) {
			$( pair[ 0 ] ).addEventListener( 'input', function () {
				var v = $( pair[ 0 ] ).value;
				if ( 'base' === pair[ 1 ] ) { v = parseInt( v, 10 ) || 15; }
				state.overrides.design[ pair[ 1 ] ] = v;
				schedulePreview();
			} );
		} );
		$( 'ttcc-logo-choose' ).addEventListener( 'click', function ( e ) { e.preventDefault(); chooseLogo(); } );
		$( 'ttcc-logo-remove' ).addEventListener( 'click', function () {
			state.overrides.design.logo = '';
			updateLogoPreview();
			schedulePreview();
		} );
	}

	// --- wire up ----------------------------------------------------------
	$( 'ttcc-generate' ).addEventListener( 'click', doGenerate );
	$( 'ttcc-save' ).addEventListener( 'click', doSave );
	$( 'ttcc-whatsapp' ).addEventListener( 'click', doWhatsApp );
	$( 'ttcc-wa-copy' ).addEventListener( 'click', copyWhatsApp );
	$( 'ttcc-wa-close' ).addEventListener( 'click', function () { $( 'ttcc-wa' ).hidden = true; } );
	$( 'ttcc-pageguides' ).addEventListener( 'change', function () {
		if ( state.doc ) { refresh( false ); }
	} );
	document.querySelectorAll( '[data-export]' ).forEach( function ( b ) {
		b.addEventListener( 'click', function () { doExport( b.dataset.export, b.dataset.variant ); } );
	} );
	$( 'ttcc-weeks' ).addEventListener( 'change', function () {
		syncEndFromWeeks();
		updateRangeLabel( null );
	} );
	$( 'ttcc-start' ).addEventListener( 'change', function () {
		syncEndFromWeeks(); // keep the same number of weeks when the Sunday moves
		updateRangeLabel( null );
	} );
	$( 'ttcc-end' ).addEventListener( 'change', function () {
		setWeeksSelectFromDates(); // a manual end date reflects as a preset or "custom"
		updateRangeLabel( null );
	} );

	// initial dates
	var sun = currentSunday();
	$( 'ttcc-start' ).value = sun;
	$( 'ttcc-end' ).value = addDays( sun, 6 );
	$( 'ttcc-weeks' ).value = '1';
	updateRangeLabel( null );
	wireDesign();
	syncDesignUI();

	pollHealth();
	setInterval( pollHealth, 30000 );

	if ( state.sheetId ) { loadSheet( state.sheetId ); }
} )();
