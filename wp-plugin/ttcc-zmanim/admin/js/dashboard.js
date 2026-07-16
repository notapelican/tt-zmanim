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
			fit_mode:     ( 'fixed' === DESIGN_DEFAULTS.fit_mode ) ? 'fixed' : 'fill',
			// Per-type typography ('' = the layout's built-in default).
			header_font:     DESIGN_DEFAULTS.header_font || '',
			header_size:     DESIGN_DEFAULTS.header_size || '',
			header_align:    DESIGN_DEFAULTS.header_align || '',
			subheader_font:  DESIGN_DEFAULTS.subheader_font || '',
			subheader_size:  DESIGN_DEFAULTS.subheader_size || '',
			subheader_align: DESIGN_DEFAULTS.subheader_align || '',
			logo_size:       DESIGN_DEFAULTS.logo_size || '',
			bsd_size:        DESIGN_DEFAULTS.bsd_size || '',
			page_margin:     DESIGN_DEFAULTS.page_margin || '',
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

	// The sheet HTML contains fixed A4 .page boxes (210×297mm ≈ 794×1123px at
	// 96dpi) with their own fit-to-page content scaling. The preview stacks the
	// pages vertically and scales the whole document as a unit, so every page
	// always keeps the locked A4 ratio — never the browser window's shape.
	var PAGE_W = 794;
	// Preview zoom: 'fit' auto-fits the pane width (clamped so pages are never
	// too small or too large); a manual slider value overrides it.
	var preview = { mode: 'fit', zoom: 1 };
	var FIT_MIN_PX = 380, FIT_MAX_PX = 900;

	function frameDoc() {
		try { return $( 'ttcc-preview' ).contentDocument; } catch ( e ) { return null; }
	}

	// Page separation + optional red boundary outlines — injected client-side
	// into the iframe document (no service round-trip, works offline).
	function decoratePreview() {
		var doc = frameDoc();
		if ( ! doc || ! doc.head ) { return; }
		var st = doc.getElementById( 'ttcc-preview-style' );
		if ( ! st ) {
			st = doc.createElement( 'style' );
			st.id = 'ttcc-preview-style';
			doc.head.appendChild( st );
		}
		var guides = $( 'ttcc-pageguides' ).checked;
		// The iframe is sized to the FULL document height (all pages), so it
		// never needs its own scrollbars — the outer pane scrolls. Force its
		// body to hide overflow so sub-pixel rounding can't spawn a scrollbar.
		st.textContent = 'html,body{overflow:hidden!important;}' + ( guides
			? 'body{background:#e8e8ec;}.page{margin:0 auto 12px;box-shadow:0 1px 6px rgba(0,0,0,.3);outline:1px solid rgba(210,50,50,.6);}'
			: 'body{background:#fff;}.page{margin:0 auto;}' );
	}

	function contentHeight() {
		var doc = frameDoc();
		if ( ! doc ) { return Math.round( PAGE_W * 297 / 210 ); }
		// +2 guards against a rounding-induced scrollbar; use the larger of the
		// two height measures since decorate margins live on <body>.
		return Math.max(
			doc.documentElement ? doc.documentElement.scrollHeight : 0,
			doc.body ? doc.body.scrollHeight : 0
		) + 2;
	}

	function renderPreviewHtml( html ) {
		var iframe = $( 'ttcc-preview' );
		iframe.setAttribute( 'scrolling', 'no' ); // no internal scrollbars (legacy but effective)
		iframe.onload = function () {
			decoratePreview();
			fitPreview();
			// The in-page fit script settles after web fonts load; re-fit once it
			// signals done (data-ttcc-fitted) so the height is measured correctly.
			var tries = 0;
			( function settle() {
				var doc = frameDoc();
				if ( doc && doc.documentElement && doc.documentElement.getAttribute( 'data-ttcc-fitted' ) === '1' ) {
					decoratePreview();
					fitPreview();
				} else if ( tries++ < 40 ) {
					setTimeout( settle, 100 );
				}
			} )();
		};
		iframe.srcdoc = html;
	}

	function previewScale() {
		if ( 'fit' !== preview.mode ) { return preview.zoom; }
		var wrap = $( 'ttcc-preview-wrap' ) || $( 'ttcc-preview-frame' ).parentNode;
		// Reserve room for a vertical scrollbar so a tall (multi-page) preview
		// never forces a second, horizontal scrollbar on the pane.
		var avail = ( ( wrap && ( wrap.clientWidth || wrap.offsetWidth ) ) || PAGE_W ) - 18;
		var target = Math.max( FIT_MIN_PX, Math.min( FIT_MAX_PX, avail ) );
		return target / PAGE_W;
	}

	function fitPreview() {
		var frame = $( 'ttcc-preview-frame' ), iframe = $( 'ttcc-preview' );
		if ( ! frame || ! iframe ) { return; }
		var scale = previewScale();
		var h = contentHeight();
		iframe.style.width = PAGE_W + 'px';
		iframe.style.height = h + 'px';
		iframe.style.transformOrigin = 'top left';
		iframe.style.transform = 'scale(' + scale + ')';
		// The sizer reserves the scaled footprint so the pane scrolls naturally.
		frame.style.width = Math.ceil( PAGE_W * scale ) + 'px';
		frame.style.height = Math.ceil( h * scale ) + 'px';
		var slider = $( 'ttcc-zoom' ), lbl = $( 'ttcc-zoom-val' );
		if ( slider && 'fit' === preview.mode ) { slider.value = Math.round( scale * 100 ); }
		if ( lbl ) { lbl.textContent = Math.round( scale * 100 ) + '%'; }
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

	/**
	 * Overrides are keyed per block ("week:<sunday>|<rule_id>") so an edit on a
	 * multi-week sheet only touches its own week. Bare legacy keys (old saved
	 * sheets) still apply sheet-wide; the first edit migrates them to the block.
	 */
	function lineRow( entry, bkey ) {
		var rid = entry.rule_id;
		var okey = bkey + '|' + rid;
		function readOv() { return state.overrides.lines[ okey ] || state.overrides.lines[ rid ] || {}; }
		function writeOv( v ) {
			delete state.overrides.lines[ rid ]; // migrate any legacy sheet-wide key
			if ( v ) { state.overrides.lines[ okey ] = v; }
			else { delete state.overrides.lines[ okey ]; }
		}
		var ov = readOv();
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
			var next = Object.assign( {}, readOv(), { time: timeInput.value } );
			delete next.suppress;
			writeOv( next );
			badge.textContent = 'override';
			badge.className = 'badge override';
			showWarn();
			schedulePreview();
		} );

		var isAdded = ( 0 === rid.indexOf( 'add:' ) );
		if ( 'zman' !== entry.kind ) {
			// Rule lines toggle suppress/restore; manually added lines are simply
			// deleted (there is no calculated line to restore behind them).
			var supBtn = el( 'button', 'button button-small', isAdded ? 'Delete' : ( ov.suppress ? 'Restore' : 'Remove' ) );
			supBtn.addEventListener( 'click', function () {
				if ( isAdded || readOv().suppress ) { writeOv( null ); }
				else { writeOv( { suppress: true } ); }
				refresh( true );
			} );
			acts.appendChild( supBtn );
		}

		if ( ( ov.time || ov.suppress ) && ! isAdded ) {
			var revBtn = el( 'button', 'button button-small', 'Revert' );
			revBtn.title = 'Revert to the calculated value';
			revBtn.addEventListener( 'click', function () {
				writeOv( null );
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

	// Distinct printed section headings present in a block, in order — the
	// add-line form offers these so a custom line lands under the right heading.
	function sectionOptions( block ) {
		var seen = [];
		( block.entries || [] ).forEach( function ( e ) {
			if ( e.section && seen.indexOf( e.section ) === -1 ) { seen.push( e.section ); }
		} );
		return seen;
	}

	// Inline "add line" editor: label + time + section (existing or new) and,
	// for week blocks, an optional day qualifier ("Wed." / "Sun.–Thurs.").
	function addLineButton( block ) {
		var wrap = el( 'div', 'ttcc-addline' );
		var btn = el( 'button', 'button button-small ttcc-add-line', '+ Add line' );
		var form = el( 'div', 'ttcc-addline-form' );
		form.hidden = true;

		var labelIn = el( 'input' );
		labelIn.type = 'text';
		labelIn.placeholder = 'Label — e.g. Special Mincha';
		labelIn.className = 'ttcc-al-label';

		var timeIn = el( 'input' );
		timeIn.type = 'time';
		timeIn.className = 'ttcc-al-time';

		var secSel = el( 'select' );
		secSel.className = 'ttcc-al-sec';
		sectionOptions( block ).forEach( function ( s ) {
			var o = el( 'option', '', s );
			o.value = s;
			secSel.appendChild( o );
		} );
		var newOpt = el( 'option', '', '＋ New section…' );
		newOpt.value = '__new__';
		secSel.appendChild( newOpt );

		var newSec = el( 'input' );
		newSec.type = 'text';
		newSec.placeholder = 'New section heading';
		newSec.className = 'ttcc-al-newsec';
		newSec.hidden = true;
		secSel.addEventListener( 'change', function () { newSec.hidden = ( '__new__' !== secSel.value ); } );

		// No-time toggle: a line without a time (e.g. a Kiddush notice) renders
		// as a plain in-section line rather than a label + dotted time.
		var noTimeWrap = el( 'label', 'ttcc-al-notime' );
		var noTime = el( 'input' );
		noTime.type = 'checkbox';
		noTimeWrap.appendChild( noTime );
		noTimeWrap.appendChild( document.createTextNode( ' No time' ) );
		noTime.addEventListener( 'change', function () { timeIn.hidden = noTime.checked; } );

		var isWeek = ( 'day' !== block.type );
		var daysIn = el( 'input' );
		daysIn.type = 'text';
		daysIn.placeholder = 'Days (optional) — e.g. Wed. or Sun.–Thurs.';
		daysIn.className = 'ttcc-al-days';

		// Position: end of section, or right after an existing line (so a new
		// time can merge into a davening group like Shacharis).
		var posSel = el( 'select' );
		posSel.className = 'ttcc-al-pos';
		var endOpt = el( 'option', '', 'At end of section' );
		endOpt.value = '';
		posSel.appendChild( endOpt );
		( block.entries || [] ).forEach( function ( e ) {
			if ( ! e.rule_id ) { return; }
			var t = e.time ? ( ' ' + e.time ) : '';
			var o = el( 'option', '', 'After: ' + ( e.label || e.rule_id ) + t );
			o.value = e.rule_id;
			posSel.appendChild( o );
		} );

		var save = el( 'button', 'button button-small button-primary', 'Add' );
		var cancel = el( 'button', 'button button-small', 'Cancel' );

		function reset() {
			labelIn.value = ''; timeIn.value = ''; newSec.value = '';
			daysIn.value = ''; secSel.selectedIndex = 0; posSel.selectedIndex = 0;
			noTime.checked = false; timeIn.hidden = false;
			newSec.hidden = ( '__new__' !== secSel.value );
			form.hidden = true; btn.hidden = false;
		}
		btn.addEventListener( 'click', function () { btn.hidden = true; form.hidden = false; labelIn.focus(); } );
		cancel.addEventListener( 'click', reset );
		save.addEventListener( 'click', function () {
			var label = labelIn.value.trim();
			if ( ! label ) { labelIn.focus(); return; }
			if ( ! noTime.checked && ! timeIn.value ) { timeIn.focus(); return; }
			var section = ( '__new__' === secSel.value ) ? newSec.value.trim() : secSel.value;
			var id = 'add:' + Date.now().toString( 36 );
			state.overrides.lines[ blockKey( block ) + '|' + id ] = {
				rule_id: id, section: section || null, label: label,
				kind: noTime.checked ? 'freetext' : 'minyan',
				day_spec: ( isWeek && daysIn.value.trim() ) ? daysIn.value.trim() : null,
				date: block.date || null, time: noTime.checked ? '' : timeIn.value,
				qualifier: null, source: 'manual',
				after: posSel.value || undefined
			};
			reset();
			refresh( true );
		} );

		form.appendChild( labelIn );
		form.appendChild( timeIn );
		form.appendChild( noTimeWrap );
		form.appendChild( secSel );
		form.appendChild( newSec );
		if ( isWeek ) { form.appendChild( daysIn ); }
		form.appendChild( posSel );
		form.appendChild( save );
		form.appendChild( cancel );
		wrap.appendChild( btn );
		wrap.appendChild( form );
		return wrap;
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
				b.appendChild( lineRow( entry, blockKey( block ) ) );
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
	// The design panel shows for BOTH layouts; controls that only affect the
	// modern layout (logo, colors, custom web fonts, week headings) hide on classic.
	function syncModernOnly() {
		var modern = ( 'modern' === state.overrides.template );
		document.querySelectorAll( '.ttcc-modern-only' ).forEach( function ( eln ) {
			eln.hidden = ! modern;
		} );
	}
	// The content font size only bites in "Fixed size" mode — in "Fill page"
	// mode the fit-to-page scaling cancels it. We leave the input enabled in
	// both modes: typing a size auto-switches to Fixed (see wireDesign), so the
	// control always visibly bites. The hint just explains the interaction.
	function syncFitMode() {
		var fixed = ( 'fixed' === state.overrides.design.fit_mode );
		var box = $( 'ttcc-base' );
		if ( box ) {
			box.title = fixed
				? 'Content font size in px. Raising it enlarges the text and tightens line spacing to fit.'
				: 'Fill page mode auto-sizes text — set a size here to switch to Fixed and use it.';
		}
	}
	function syncDesignUI() {
		var d = state.overrides.design;
		$( 'ttcc-layout' ).value = state.overrides.template || 'classic';
		syncModernOnly();
		$( 'ttcc-heading-font' ).value = d.heading_font;
		$( 'ttcc-body-font' ).value = d.body_font;
		$( 'ttcc-font-source' ).value = d.font_source || 'google';
		$( 'ttcc-custom-heading' ).value = d.custom_heading || '';
		$( 'ttcc-custom-body' ).value = d.custom_body || '';
		$( 'ttcc-base' ).value = d.base;
		if ( $( 'ttcc-fit-mode' ) ) {
			$( 'ttcc-fit-mode' ).value = d.fit_mode || 'fill';
			syncFitMode();
		}
		$( 'ttcc-header-font' ).value = d.header_font || '';
		$( 'ttcc-header-size' ).value = d.header_size || '';
		$( 'ttcc-header-align' ).value = d.header_align || '';
		$( 'ttcc-subheader-font' ).value = d.subheader_font || '';
		$( 'ttcc-subheader-size' ).value = d.subheader_size || '';
		$( 'ttcc-subheader-align' ).value = d.subheader_align || '';
		$( 'ttcc-logo-size' ).value = d.logo_size || 56;
		if ( $( 'ttcc-bsd-size' ) ) { $( 'ttcc-bsd-size' ).value = d.bsd_size || ''; }
		if ( $( 'ttcc-page-margin' ) ) { $( 'ttcc-page-margin' ).value = d.page_margin || ''; }
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
			syncModernOnly();
			if ( state.doc ) { refresh( false ); }
		} );
		[ [ 'ttcc-heading-font', 'heading_font' ], [ 'ttcc-body-font', 'body_font' ],
		  [ 'ttcc-font-source', 'font_source' ], [ 'ttcc-custom-heading', 'custom_heading' ], [ 'ttcc-custom-body', 'custom_body' ],
		  [ 'ttcc-base', 'base' ], [ 'ttcc-fit-mode', 'fit_mode' ],
		  [ 'ttcc-header-font', 'header_font' ], [ 'ttcc-header-size', 'header_size' ], [ 'ttcc-header-align', 'header_align' ],
		  [ 'ttcc-subheader-font', 'subheader_font' ], [ 'ttcc-subheader-size', 'subheader_size' ], [ 'ttcc-subheader-align', 'subheader_align' ],
		  [ 'ttcc-logo-size', 'logo_size' ],
		  [ 'ttcc-bsd-size', 'bsd_size' ], [ 'ttcc-page-margin', 'page_margin' ],
		  [ 'ttcc-text-color', 'text_color' ],
		  [ 'ttcc-callout-bg', 'callout_bg' ], [ 'ttcc-callout-text', 'callout_text' ] ]
		.forEach( function ( pair ) {
			$( pair[ 0 ] ).addEventListener( 'input', function () {
				var v = $( pair[ 0 ] ).value;
				if ( 'base' === pair[ 1 ] ) {
					v = parseInt( v, 10 ) || 15;
					if ( v < 8 ) { v = 8; } else if ( v > 40 ) { v = 40; }
					// Picking a font size only takes effect in Fixed mode, so
					// switch there automatically — the control always bites.
					state.overrides.design.fit_mode = 'fixed';
					if ( $( 'ttcc-fit-mode' ) ) { $( 'ttcc-fit-mode' ).value = 'fixed'; }
					syncFitMode();
				}
				state.overrides.design[ pair[ 1 ] ] = v;
				if ( 'fit_mode' === pair[ 1 ] ) { syncFitMode(); }
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

	// --- style presets ----------------------------------------------------
	// Named, site-wide design presets (fonts/sizes/logo/colors/layout). Applying
	// one copies it into the current sheet's design; "Default" marks the preset
	// new (unsaved) sheets start from.
	var presets = { default: '', items: {} };
	function populatePresetSelect( selected ) {
		var sel = $( 'ttcc-preset' );
		if ( ! sel ) { return; }
		sel.innerHTML = '';
		var none = el( 'option', '', '— none —' ); none.value = ''; sel.appendChild( none );
		Object.keys( presets.items ).sort().forEach( function ( name ) {
			var o = el( 'option', '', name + ( name === presets.default ? ' (default)' : '' ) );
			o.value = name;
			sel.appendChild( o );
		} );
		sel.value = selected || '';
		$( 'ttcc-preset-default' ).checked = ( sel.value && sel.value === presets.default );
	}
	function applyPresetToState( name ) {
		var p = presets.items[ name ];
		if ( ! p ) { return; }
		state.overrides.template = ( 'modern' === p.template ) ? 'modern' : 'classic';
		state.overrides.design = Object.assign( defaultDesign(), p.design || {} );
	}
	function loadPresets() {
		if ( ! $( 'ttcc-preset' ) ) { return; }
		api( '/presets', 'GET' ).then( function ( d ) {
			presets = { default: d.default || '', items: d.items || {} };
			populatePresetSelect( presets.default );
			// A fresh, never-saved sheet inherits the default preset's look.
			if ( ! state.sheetId && presets.default && presets.items[ presets.default ] ) {
				applyPresetToState( presets.default );
				syncDesignUI();
				if ( state.doc ) { refresh( false ); }
			}
		} ).catch( function () { /* presets are optional; ignore load errors */ } );
	}
	function wirePresets() {
		if ( ! $( 'ttcc-preset' ) ) { return; }
		$( 'ttcc-preset-apply' ).addEventListener( 'click', function () {
			var name = $( 'ttcc-preset' ).value;
			if ( ! name ) { return; }
			applyPresetToState( name );
			syncDesignUI();
			if ( state.doc ) { refresh( false ); }
		} );
		$( 'ttcc-preset-save' ).addEventListener( 'click', function () {
			var current = $( 'ttcc-preset' ).value;
			var name = ( window.prompt( 'Save current design as preset named:', current ) || '' ).trim();
			if ( ! name ) { return; }
			api( '/presets', 'POST', { name: name, template: state.overrides.template, design: state.overrides.design } )
				.then( function ( d ) {
					presets = { default: d.default || '', items: d.items || {} };
					populatePresetSelect( name );
				} ).catch( function ( e ) { window.alert( 'Save failed: ' + e.message ); } );
		} );
		$( 'ttcc-preset-delete' ).addEventListener( 'click', function () {
			var name = $( 'ttcc-preset' ).value;
			if ( ! name || ! window.confirm( 'Delete preset "' + name + '"?' ) ) { return; }
			api( '/presets/delete', 'POST', { name: name } ).then( function ( d ) {
				presets = { default: d.default || '', items: d.items || {} };
				populatePresetSelect( '' );
			} ).catch( function ( e ) { window.alert( 'Delete failed: ' + e.message ); } );
		} );
		$( 'ttcc-preset-default' ).addEventListener( 'change', function () {
			var name = $( 'ttcc-preset' ).value;
			var want = ( $( 'ttcc-preset-default' ).checked && name ) ? name : '';
			api( '/presets/default', 'POST', { name: want } ).then( function ( d ) {
				presets = { default: d.default || '', items: d.items || {} };
				populatePresetSelect( name );
			} ).catch( function ( e ) { window.alert( 'Failed: ' + e.message ); } );
		} );
	}

	// --- wire up ----------------------------------------------------------
	$( 'ttcc-generate' ).addEventListener( 'click', doGenerate );
	$( 'ttcc-save' ).addEventListener( 'click', doSave );
	$( 'ttcc-whatsapp' ).addEventListener( 'click', doWhatsApp );
	$( 'ttcc-wa-copy' ).addEventListener( 'click', copyWhatsApp );
	$( 'ttcc-wa-close' ).addEventListener( 'click', function () { $( 'ttcc-wa' ).hidden = true; } );
	// Keep the A4 preview fitted to the pane width as the window resizes.
	var fitTimer = null;
	window.addEventListener( 'resize', function () {
		clearTimeout( fitTimer );
		fitTimer = setTimeout( fitPreview, 150 );
	} );
	$( 'ttcc-pageguides' ).addEventListener( 'change', function () {
		decoratePreview(); // client-side only — no service round-trip
		fitPreview();
	} );
	// Preview zoom: slider takes manual control; "Fit width" returns to auto.
	if ( $( 'ttcc-zoom' ) ) {
		$( 'ttcc-zoom' ).addEventListener( 'input', function () {
			preview.mode = 'manual';
			preview.zoom = Math.max( 0.4, Math.min( 2, parseInt( $( 'ttcc-zoom' ).value, 10 ) / 100 || 1 ) );
			fitPreview();
		} );
	}
	if ( $( 'ttcc-zoom-fit' ) ) {
		$( 'ttcc-zoom-fit' ).addEventListener( 'click', function () {
			preview.mode = 'fit';
			fitPreview();
		} );
	}
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
	wirePresets();
	syncDesignUI();
	loadPresets();

	pollHealth();
	setInterval( pollHealth, 30000 );

	if ( state.sheetId ) { loadSheet( state.sheetId ); }
} )();
