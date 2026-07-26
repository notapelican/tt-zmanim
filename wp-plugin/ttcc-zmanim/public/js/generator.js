/**
 * Front-end timesheet generator ([ttcc_generator]).
 *
 * A deliberately small sibling of the wp-admin dashboard editor: pick a week (or
 * a run of weeks), optionally adjust minyan times / add lines & notes, then
 * export a PDF, an image, or the WhatsApp broadcast text.
 *
 * Same contract as the admin editor — the engine (via the sheet service) owns
 * every time; this UI only records overrides keyed by rule_id (edit / suppress /
 * add) plus block-level note edits, and asks the service to re-render. It never
 * computes or re-rounds a time. Styling is not exposed at all: the server
 * applies the site's house design, and the only choice here is Classic vs Modern.
 *
 * Override keys are block-scoped ("week:<sunday>|<rule_id>"), so edits survive a
 * change of range — an edit only ever applies to its own week.
 */
( function () {
	'use strict';

	var PAGE_W = 794;              // A4 width at 96dpi; the sheet HTML is fixed-width.
	var FIT_MIN = 260, FIT_MAX = 900;
	var DEBOUNCE_MS = 400;

	function el( tag, cls, text ) {
		var n = document.createElement( tag );
		if ( cls ) { n.className = cls; }
		if ( undefined !== text && null !== text ) { n.textContent = text; }
		return n;
	}
	function pad( n ) { return ( n < 10 ? '0' : '' ) + n; }
	function isoOf( d ) { return d.getFullYear() + '-' + pad( d.getMonth() + 1 ) + '-' + pad( d.getDate() ); }
	function addDays( iso, n ) {
		var d = new Date( iso + 'T00:00:00' );
		d.setDate( d.getDate() + n );
		return isoOf( d );
	}
	function sundayOf( iso ) {
		var d = new Date( iso + 'T00:00:00' );
		if ( isNaN( d.getTime() ) ) { return ''; }
		d.setDate( d.getDate() - d.getDay() );
		return isoOf( d );
	}
	function currentSunday() {
		var d = new Date();
		d.setDate( d.getDate() - d.getDay() );
		return isoOf( d );
	}
	/** "2026-08-02" -> "2 Aug 2026" (locale-formatted where available). */
	function prettyDate( iso ) {
		var d = new Date( iso + 'T00:00:00' );
		if ( isNaN( d.getTime() ) ) { return iso; }
		try {
			return d.toLocaleDateString( undefined, { day: 'numeric', month: 'short', year: 'numeric' } );
		} catch ( e ) {
			return iso;
		}
	}

	function boot( root, cfg ) {
		var state = {
			start: sundayOf( cfg.sunday ) || currentSunday(),
			weeks: Math.max( 1, Math.min( 4, parseInt( cfg.weeks, 10 ) || 1 ) ),
			template: ( 'modern' === cfg.template ) ? 'modern' : 'classic',
			overrides: { lines: {}, notes: {} },
			originalNotes: {},   // blockKey -> notes as the engine calculated them
			hiddenLines: {},     // override key -> the entry that was hidden (so it can come back)
			doc: null,
			busy: 0,
			editing: false,
			zoom: { mode: 'fit', scale: 1 }
		};

		var q = function ( sel ) { return root.querySelector( sel ); };
		var qa = function ( sel ) { return Array.prototype.slice.call( root.querySelectorAll( sel ) ); };
		var ui = {
			start: q( '[data-role="start"]' ),
			summary: q( '[data-role="summary"]' ),
			status: q( '[data-role="status"]' ),
			alert: q( '[data-role="alert"]' ),
			editor: q( '[data-role="editor"]' ),
			editorBody: q( '[data-role="editor-body"]' ),
			editToggle: q( '[data-role="edit-toggle"]' ),
			reset: q( '[data-role="reset"]' ),
			frame: q( '[data-role="frame"]' ),
			preview: q( '[data-role="preview"]' ),
			zoomVal: q( '[data-role="zoom-val"]' ),
			engine: q( '[data-role="engine"]' ),
			wa: q( '[data-role="wa"]' ),
			waText: q( '[data-role="wa-text"]' ),
			waStatus: q( '[data-role="wa-status"]' ),
			waOpen: q( '[data-role="wa-open"]' )
		};

		// --- plumbing -------------------------------------------------------

		function api( path, body ) {
			var headers = { 'Content-Type': 'application/json' };
			if ( cfg.nonce ) { headers['X-WP-Nonce'] = cfg.nonce; }
			return fetch( cfg.restUrl + path, {
				method: 'POST',
				headers: headers,
				credentials: 'same-origin',
				body: JSON.stringify( body )
			} ).then( function ( res ) {
				return res.json().catch( function () { return null; } ).then( function ( data ) {
					if ( ! res.ok ) {
						var err = new Error( ( data && ( data.message || data.detail ) ) || ( 'HTTP ' + res.status ) );
						err.status = res.status;
						throw err;
					}
					return data;
				} );
			} );
		}

		/**
		 * Note entries left empty by toggling a checkbox back and forth are pruned:
		 * an empty edit set is the same as no edit, and sending one would defeat
		 * the server's cache of unedited sheets.
		 */
		function payload() {
			var notes = {};
			Object.keys( state.overrides.notes ).forEach( function ( key ) {
				var e = state.overrides.notes[ key ];
				var added = ( e.added || [] ).filter( function ( t ) { return t && t.trim(); } );
				if ( ( e.removed || [] ).length || added.length ) {
					notes[ key ] = { removed: e.removed || [], added: added };
				}
			} );
			return {
				start: state.start,
				weeks: state.weeks,
				template: state.template,
				overrides: { lines: state.overrides.lines, notes: notes }
			};
		}

		function setBusy( on, message ) {
			state.busy += on ? 1 : -1;
			if ( state.busy < 0 ) { state.busy = 0; }
			var busy = state.busy > 0;
			ui.status.textContent = busy ? ( message || cfg.i18n.working ) : '';
			ui.status.className = 'tg-status' + ( busy ? ' is-busy' : '' );
			qa( '[data-busy-disable]' ).forEach( function ( b ) { b.disabled = busy; } );
		}

		function say( message ) {
			ui.status.className = 'tg-status';
			ui.status.textContent = message || '';
		}

		function fail( message ) {
			ui.alert.hidden = false;
			ui.alert.textContent = message;
		}
		function clearFail() {
			ui.alert.hidden = true;
			ui.alert.textContent = '';
		}

		function hasEdits() {
			if ( Object.keys( state.overrides.lines ).length ) { return true; }
			return Object.keys( payload().overrides.notes ).length > 0;
		}

		// --- range ----------------------------------------------------------

		function endDate() { return addDays( state.start, state.weeks * 7 - 1 ); }

		function weekTitle( block ) { return block.parsha || block.title || ''; }

		function updateSummary() {
			var range = prettyDate( state.start ) + ' – ' + prettyDate( endDate() );
			var span = state.weeks + ' ' + ( 1 === state.weeks ? cfg.i18n.week : cfg.i18n.weeks );
			var parshios = '';
			if ( state.doc && state.doc.blocks ) {
				var wk = state.doc.blocks.filter( function ( b ) { return 'week' === b.type; } );
				if ( wk.length ) {
					var first = weekTitle( wk[0] ), last = weekTitle( wk[ wk.length - 1 ] );
					parshios = ( wk.length > 1 && first && last ) ? ( first + ' → ' + last ) : first;
				}
			}
			ui.summary.innerHTML = '';
			if ( parshios ) {
				ui.summary.appendChild( el( 'b', '', parshios ) );
				ui.summary.appendChild( document.createTextNode( ' · ' ) );
			}
			ui.summary.appendChild( document.createTextNode( span + ' · ' + range ) );
		}

		function syncControls() {
			ui.start.value = state.start;
			qa( '[data-weeks]' ).forEach( function ( b ) {
				b.setAttribute( 'aria-pressed', String( parseInt( b.dataset.weeks, 10 ) === state.weeks ) );
			} );
			qa( '[data-style]' ).forEach( function ( b ) {
				b.setAttribute( 'aria-pressed', String( b.dataset.style === state.template ) );
			} );
			ui.editToggle.setAttribute( 'aria-expanded', String( state.editing ) );
			ui.editToggle.textContent = state.editing ? cfg.i18n.hideEditor : cfg.i18n.showEditor;
			ui.reset.hidden = ! hasEdits();
			updateSummary();
		}

		// --- preview --------------------------------------------------------

		function frameDoc() {
			try { return ui.preview.contentDocument; } catch ( e ) { return null; }
		}

		function contentHeight() {
			var doc = frameDoc();
			if ( ! doc ) { return Math.round( PAGE_W * 297 / 210 ); }
			return Math.max(
				doc.documentElement ? doc.documentElement.scrollHeight : 0,
				doc.body ? doc.body.scrollHeight : 0
			) + 2;
		}

		/** Stack the A4 pages with a little separation; no inner scrollbars. */
		function decorate() {
			var doc = frameDoc();
			if ( ! doc || ! doc.head ) { return; }
			var st = doc.getElementById( 'ttcc-gen-style' );
			if ( ! st ) {
				st = doc.createElement( 'style' );
				st.id = 'ttcc-gen-style';
				doc.head.appendChild( st );
			}
			st.textContent = 'html,body{overflow:hidden!important;background:#fff;}' +
				'.page{margin:0 auto 10px;box-shadow:0 0 0 1px rgba(20,29,51,.10);}' +
				'.page:last-child{margin-bottom:0;}';
		}

		function scale() {
			if ( 'fit' !== state.zoom.mode ) { return state.zoom.scale; }
			var pane = ui.frame.parentNode;
			var avail = ( ( pane && ( pane.clientWidth || pane.offsetWidth ) ) || PAGE_W ) - 4;
			// Never wider than the pane: on a phone the pane is narrower than
			// FIT_MIN, and a floor there would clip the sheet's right edge.
			var target = Math.min( avail, Math.max( FIT_MIN, Math.min( FIT_MAX, avail ) ) );
			return Math.max( 0.2, target / PAGE_W );
		}

		function fit() {
			var s = scale(), h = contentHeight();
			ui.preview.style.width = PAGE_W + 'px';
			ui.preview.style.height = h + 'px';
			ui.preview.style.transformOrigin = 'top left';
			ui.preview.style.transform = 'scale(' + s + ')';
			ui.frame.style.width = Math.ceil( PAGE_W * s ) + 'px';
			ui.frame.style.height = Math.ceil( h * s ) + 'px';
			ui.zoomVal.textContent = Math.round( s * 100 ) + '%';
		}

		function showHtml( html ) {
			ui.preview.setAttribute( 'scrolling', 'no' );
			ui.preview.onload = function () {
				decorate();
				fit();
				// The sheet's own fit-to-page script settles after web fonts load
				// and flags data-ttcc-fitted; re-measure once it does.
				var tries = 0;
				( function settle() {
					var doc = frameDoc();
					if ( doc && doc.documentElement && '1' === doc.documentElement.getAttribute( 'data-ttcc-fitted' ) ) {
						decorate();
						fit();
					} else if ( tries++ < 40 ) {
						setTimeout( settle, 100 );
					}
				} )();
			};
			ui.preview.srcdoc = html;
		}

		var refreshTimer = null;
		function scheduleRefresh( rebuild ) {
			clearTimeout( refreshTimer );
			refreshTimer = setTimeout( function () { refresh( rebuild ); }, DEBOUNCE_MS );
		}

		var seq = 0;
		function refresh( rebuildEditor ) {
			clearTimeout( refreshTimer );
			setBusy( true, cfg.i18n.building );
			var mine = ++seq;
			return api( '/preview', payload() ).then( function ( data ) {
				// A quick run of changes can land out of order; only the newest wins.
				if ( mine !== seq ) { setBusy( false ); return; }
				clearFail();
				state.doc = data.doc;
				rememberOriginalNotes( data.doc );
				showHtml( data.html );
				if ( rebuildEditor ) { buildEditor(); }
				ui.engine.textContent = data.engine_version ? ( 'engine ' + data.engine_version ) : '';
				setBusy( false );
				syncControls();
			} ).catch( function ( e ) {
				setBusy( false );
				if ( mine !== seq ) { return; }
				fail( ( 429 === e.status ? cfg.i18n.throttled : cfg.i18n.previewFailed ) + ' ' + e.message );
			} );
		}

		// --- editor ---------------------------------------------------------

		function blockKey( b ) {
			return ( 'day' === b.type ) ? ( 'day:' + ( b.date || '' ) ) : ( 'week:' + ( b.civil_start || '' ) );
		}

		/**
		 * Notes are edited as "hide these calculated ones, append these new ones",
		 * so the editor needs the calculated list. A block with no note edits
		 * shows exactly that list already, so capture it then — no extra request.
		 */
		function rememberOriginalNotes( doc ) {
			( doc && doc.blocks ? doc.blocks : [] ).forEach( function ( b ) {
				var key = blockKey( b );
				if ( ! state.overrides.notes[ key ] ) {
					state.originalNotes[ key ] = ( b.notes || [] ).slice();
				}
			} );
		}

		function boundWarning( time, bound ) {
			if ( ! bound || ! bound.time || ! time ) { return ''; }
			if ( 'not_before' === bound.direction && time < bound.time ) {
				return cfg.i18n.earlierThan.replace( '%1$s', bound.zman ).replace( '%2$s', bound.time );
			}
			if ( 'not_after' === bound.direction && time > bound.time ) {
				return cfg.i18n.laterThan.replace( '%1$s', bound.zman ).replace( '%2$s', bound.time );
			}
			return '';
		}

		function lineRow( entry, bkey ) {
			var rid = entry.rule_id || '';
			var editable = '' !== rid;
			var key = bkey + '|' + rid;
			var isAdded = ( 0 === rid.indexOf( 'add:' ) );
			var isZman = ( 'zman' === entry.kind );

			function ov() { return state.overrides.lines[ key ] || {}; }
			function setOv( v ) {
				if ( v ) { state.overrides.lines[ key ] = v; } else { delete state.overrides.lines[ key ]; }
				ui.reset.hidden = ! hasEdits();
			}

			var current = ov();
			var row = el( 'div', 'tg-line' );

			var label = el( 'div', 'tg-line-label' );
			label.appendChild( document.createTextNode( entry.label || '' ) );
			if ( entry.day_spec ) {
				label.appendChild( el( 'span', 'tg-line-days', ' ' + entry.day_spec ) );
			}
			// The tag always exists (hidden on a plain calculated line) so an edit
			// can light it up without rebuilding the row.
			var tag = el( 'span', 'tg-tag' );
			if ( 'override' === entry.source ) {
				tag.className = 'tg-tag is-override';
				tag.textContent = cfg.i18n.tagAdjusted;
			} else if ( 'manual' === entry.source ) {
				tag.className = 'tg-tag is-manual';
				tag.textContent = cfg.i18n.tagAdded;
			} else {
				tag.hidden = true;
			}
			label.appendChild( tag );
			row.appendChild( label );

			var time = el( 'input' );
			time.type = 'time';
			time.value = entry.time || '';
			time.disabled = isZman || ! editable;   // astronomical times are never editable
			time.setAttribute( 'aria-label', ( entry.label || '' ) + ' — ' + cfg.i18n.time );
			if ( time.disabled ) { time.title = cfg.i18n.tagZman; }
			row.appendChild( time );

			var warn = el( 'div', 'tg-warn' );
			var acts = el( 'div', 'tg-line-acts' );

			/**
			 * Only warn about a halachic bound on a time this visitor typed. The
			 * engine's own lines sometimes sit a minute either side of their bound
			 * by design, and flagging those would read as "you broke something".
			 */
			function showWarning() {
				var msg = ov().time ? boundWarning( time.value, entry.bound ) : '';
				warn.textContent = msg ? ( '⚠ ' + msg ) : '';
			}

			/** A calculated line that has been edited can always be put back. */
			function addRevert() {
				if ( isAdded || acts.querySelector( '[data-revert]' ) ) { return; }
				var revert = el( 'button', 'tg-mini', cfg.i18n.revert );
				revert.type = 'button';
				revert.title = cfg.i18n.revertHint;
				revert.setAttribute( 'data-revert', '1' );
				revert.addEventListener( 'click', function () {
					setOv( null );
					refresh( true );
				} );
				acts.appendChild( revert );
			}

			time.addEventListener( 'input', function () {
				if ( ! time.value ) { return; }
				var next = isAdded ? Object.assign( {}, ov(), { time: time.value } ) : { time: time.value };
				delete next.suppress;
				setOv( next );
				tag.hidden = false;
				tag.className = 'tg-tag is-override';
				tag.textContent = cfg.i18n.tagAdjusted;
				addRevert();
				showWarning();
				scheduleRefresh( false );
			} );

			if ( editable && ! isZman ) {
				var toggle = el( 'button', 'tg-mini' + ( isAdded ? ' is-danger' : '' ),
					isAdded ? cfg.i18n.deleteLine : cfg.i18n.removeLine );
				toggle.type = 'button';
				toggle.addEventListener( 'click', function () {
					if ( isAdded ) {
						setOv( null );
					} else {
						// Remember the line: once suppressed it is gone from the
						// engine's output, so the editor has to carry it to offer
						// "restore" (see hiddenLinesGroup).
						state.hiddenLines[ key ] = entry;
						setOv( { suppress: true } );
					}
					refresh( true );
				} );
				acts.appendChild( toggle );
			}

			if ( current.time ) {
				addRevert();
			}

			row.appendChild( acts );
			row.appendChild( warn );
			showWarning();
			return row;
		}

		/** Distinct printed section headings in a block, in order. */
		function sectionsOf( block ) {
			var seen = [];
			( block.entries || [] ).forEach( function ( e ) {
				if ( e.section && -1 === seen.indexOf( e.section ) ) { seen.push( e.section ); }
			} );
			return seen;
		}

		function addLineForm( block ) {
			var wrap = el( 'div', 'tg-add' );
			var open = el( 'button', 'tg-mini', cfg.i18n.addLine );
			open.type = 'button';
			var form = el( 'div', 'tg-add-form' );
			form.hidden = true;

			var rowA = el( 'div', 'tg-row' );
			var labelIn = el( 'input' );
			labelIn.type = 'text';
			labelIn.placeholder = cfg.i18n.labelPlaceholder;
			labelIn.setAttribute( 'aria-label', cfg.i18n.labelPlaceholder );
			var timeIn = el( 'input' );
			timeIn.type = 'time';
			timeIn.setAttribute( 'aria-label', cfg.i18n.time );
			var noTimeWrap = el( 'label', 'tg-check' );
			var noTime = el( 'input' );
			noTime.type = 'checkbox';
			noTimeWrap.appendChild( noTime );
			noTimeWrap.appendChild( document.createTextNode( cfg.i18n.noTime ) );
			noTime.addEventListener( 'change', function () { timeIn.hidden = noTime.checked; } );
			rowA.appendChild( labelIn );
			rowA.appendChild( timeIn );
			rowA.appendChild( noTimeWrap );

			var rowB = el( 'div', 'tg-row' );
			var sectionSel = el( 'select' );
			sectionSel.setAttribute( 'aria-label', cfg.i18n.section );
			sectionsOf( block ).forEach( function ( s ) {
				var o = el( 'option', '', s );
				o.value = s;
				sectionSel.appendChild( o );
			} );
			var newOpt = el( 'option', '', cfg.i18n.newSection );
			newOpt.value = '__new__';
			sectionSel.appendChild( newOpt );
			var newSection = el( 'input' );
			newSection.type = 'text';
			newSection.placeholder = cfg.i18n.newSectionPlaceholder;
			newSection.setAttribute( 'aria-label', cfg.i18n.newSectionPlaceholder );
			newSection.hidden = true;
			sectionSel.addEventListener( 'change', function () {
				newSection.hidden = ( '__new__' !== sectionSel.value );
			} );
			rowB.appendChild( sectionSel );
			rowB.appendChild( newSection );

			var rowC = el( 'div', 'tg-row' );
			// Position: appended to the section, or straight after an existing line
			// (which merges it into that printed davening group).
			var posSel = el( 'select' );
			posSel.setAttribute( 'aria-label', cfg.i18n.position );
			var endOpt = el( 'option', '', cfg.i18n.atSectionEnd );
			endOpt.value = '';
			posSel.appendChild( endOpt );
			( block.entries || [] ).forEach( function ( e ) {
				if ( ! e.rule_id ) { return; }
				var o = el( 'option', '', cfg.i18n.after + ' ' + ( e.label || e.rule_id ) + ( e.time ? ( ' ' + e.time ) : '' ) );
				o.value = e.rule_id;
				posSel.appendChild( o );
			} );
			rowC.appendChild( posSel );

			var isWeek = ( 'day' !== block.type );
			var daysIn = null;
			if ( isWeek ) {
				daysIn = el( 'input' );
				daysIn.type = 'text';
				daysIn.placeholder = cfg.i18n.daysPlaceholder;
				daysIn.setAttribute( 'aria-label', cfg.i18n.daysPlaceholder );
				rowC.appendChild( daysIn );
			}

			var rowD = el( 'div', 'tg-row tg-row-end' );
			var cancel = el( 'button', 'tg-mini', cfg.i18n.cancel );
			cancel.type = 'button';
			var save = el( 'button', 'tg-mini', cfg.i18n.add );
			save.type = 'button';
			rowD.appendChild( cancel );
			rowD.appendChild( save );

			function reset() {
				labelIn.value = '';
				timeIn.value = '';
				newSection.value = '';
				if ( daysIn ) { daysIn.value = ''; }
				sectionSel.selectedIndex = 0;
				posSel.selectedIndex = 0;
				noTime.checked = false;
				timeIn.hidden = false;
				newSection.hidden = true;
				form.hidden = true;
				open.hidden = false;
			}

			open.addEventListener( 'click', function () {
				open.hidden = true;
				form.hidden = false;
				labelIn.focus();
			} );
			cancel.addEventListener( 'click', reset );
			save.addEventListener( 'click', function () {
				var label = labelIn.value.trim();
				if ( ! label ) { labelIn.focus(); return; }
				if ( ! noTime.checked && ! timeIn.value ) { timeIn.focus(); return; }
				var section = ( '__new__' === sectionSel.value ) ? newSection.value.trim() : sectionSel.value;
				var id = 'add:' + Date.now().toString( 36 );
				var line = {
					rule_id: id,
					section: section || null,
					label: label,
					kind: noTime.checked ? 'freetext' : 'minyan',
					day_spec: ( daysIn && daysIn.value.trim() ) ? daysIn.value.trim() : null,
					date: block.date || null,
					time: noTime.checked ? '' : timeIn.value,
					qualifier: null,
					source: 'manual'
				};
				if ( posSel.value ) { line.after = posSel.value; }
				state.overrides.lines[ blockKey( block ) + '|' + id ] = line;
				reset();
				refresh( true );
			} );

			form.appendChild( rowA );
			form.appendChild( rowB );
			form.appendChild( rowC );
			form.appendChild( rowD );
			wrap.appendChild( open );
			wrap.appendChild( form );
			return wrap;
		}

		/**
		 * Lines this visitor hid. They are absent from the engine's output, so the
		 * editor lists them separately with a way to bring them back.
		 */
		function hiddenLinesGroup( block ) {
			var prefix = blockKey( block ) + '|';
			var keys = Object.keys( state.overrides.lines ).filter( function ( key ) {
				return 0 === key.indexOf( prefix ) && state.overrides.lines[ key ].suppress;
			} );
			if ( ! keys.length ) { return null; }

			var wrap = el( 'div', 'tg-hidden' );
			wrap.appendChild( el( 'div', 'tg-section', cfg.i18n.hiddenLines ) );
			keys.forEach( function ( key ) {
				var was = state.hiddenLines[ key ] || {};
				var row = el( 'div', 'tg-line is-off' );
				var label = el( 'div', 'tg-line-label' );
				label.appendChild( document.createTextNode( was.label || key.slice( prefix.length ) ) );
				if ( was.day_spec ) { label.appendChild( el( 'span', 'tg-line-days', ' ' + was.day_spec ) ); }
				if ( was.time ) { label.appendChild( el( 'span', 'tg-line-days', ' · ' + was.time ) ); }
				row.appendChild( label );
				var acts = el( 'div', 'tg-line-acts' );
				var restore = el( 'button', 'tg-mini', cfg.i18n.restoreLine );
				restore.type = 'button';
				restore.addEventListener( 'click', function () {
					delete state.overrides.lines[ key ];
					delete state.hiddenLines[ key ];
					ui.reset.hidden = ! hasEdits();
					refresh( true );
				} );
				acts.appendChild( restore );
				row.appendChild( acts );
				wrap.appendChild( row );
			} );
			return wrap;
		}

		function notesEditor( block ) {
			var key = blockKey( block );
			var wrap = el( 'div', 'tg-notes' );
			wrap.appendChild( el( 'div', 'tg-section', cfg.i18n.notes ) );

			var edit = state.overrides.notes[ key ] || { removed: [], added: [] };
			var originals = state.originalNotes[ key ] || ( block.notes || [] );

			function entry() {
				var e = state.overrides.notes[ key ] || { removed: [], added: [] };
				e.removed = e.removed || [];
				e.added = e.added || [];
				state.overrides.notes[ key ] = e;
				return e;
			}

			originals.forEach( function ( text, idx ) {
				var line = el( 'div', 'tg-note' );
				var label = el( 'label' );
				var cb = el( 'input' );
				cb.type = 'checkbox';
				cb.checked = ( -1 === ( edit.removed || [] ).indexOf( idx ) );
				cb.addEventListener( 'change', function () {
					var e = entry();
					var at = e.removed.indexOf( idx );
					if ( cb.checked && at > -1 ) { e.removed.splice( at, 1 ); }
					if ( ! cb.checked && -1 === at ) { e.removed.push( idx ); }
					ui.reset.hidden = ! hasEdits();
					scheduleRefresh( false );
				} );
				label.appendChild( cb );
				label.appendChild( el( 'span', '', text ) );
				line.appendChild( label );
				wrap.appendChild( line );
			} );

			( edit.added || [] ).forEach( function ( text, i ) {
				var line = el( 'div', 'tg-note' );
				var ta = el( 'textarea' );
				ta.rows = 2;
				ta.value = text;
				ta.setAttribute( 'aria-label', cfg.i18n.noteText );
				ta.addEventListener( 'input', function () {
					entry().added[ i ] = ta.value;
					scheduleRefresh( false );
				} );
				var del = el( 'button', 'tg-mini is-danger', '×' );
				del.type = 'button';
				del.title = cfg.i18n.removeNote;
				del.setAttribute( 'aria-label', cfg.i18n.removeNote );
				del.addEventListener( 'click', function () {
					entry().added.splice( i, 1 );
					refresh( true );
				} );
				line.appendChild( ta );
				line.appendChild( del );
				wrap.appendChild( line );
			} );

			var add = el( 'button', 'tg-mini', cfg.i18n.addNote );
			add.type = 'button';
			add.addEventListener( 'click', function () {
				entry().added.push( '' );
				refresh( true );
			} );
			wrap.appendChild( add );
			return wrap;
		}

		function buildEditor() {
			var body = ui.editorBody;
			body.innerHTML = '';
			var doc = state.doc;
			if ( ! doc || ! doc.blocks || ! doc.blocks.length ) {
				body.appendChild( el( 'p', 'tg-empty', cfg.i18n.nothingToEdit ) );
				return;
			}
			doc.blocks.forEach( function ( block ) {
				var wrap = el( 'div', 'tg-block' );
				wrap.appendChild( el( 'h4', 'tg-block-title',
					block.title || ( block.weekday ? ( block.weekday + ' ' + ( block.hebrew_date || '' ) ) : '' ) ) );

				var section = ' ';
				( block.entries || [] ).forEach( function ( entry ) {
					var sec = entry.section || '';
					if ( sec !== section ) {
						section = sec;
						if ( sec ) { wrap.appendChild( el( 'div', 'tg-section', sec ) ); }
					}
					wrap.appendChild( lineRow( entry, blockKey( block ) ) );
				} );

				var hidden = hiddenLinesGroup( block );
				if ( hidden ) { wrap.appendChild( hidden ); }
				wrap.appendChild( addLineForm( block ) );
				wrap.appendChild( notesEditor( block ) );
				body.appendChild( wrap );
			} );
		}

		function setEditing( on ) {
			state.editing = !! on;
			root.classList.toggle( 'is-editing', state.editing );
			ui.editor.hidden = ! state.editing;
			if ( state.editing ) { buildEditor(); }
			syncControls();
			fit();
		}

		// --- exports --------------------------------------------------------

		/**
		 * Downloads POST to admin-ajax through a throwaway form: the response is a
		 * file (Content-Disposition), and a POST body keeps long override sets off
		 * the query string.
		 */
		function download( kind ) {
			var form = document.createElement( 'form' );
			form.method = 'POST';
			form.action = cfg.ajaxUrl;
			// _blank so a failure (which arrives as an HTML error page) is visible;
			// a successful download closes the tab on its own.
			form.target = '_blank';
			form.style.display = 'none';
			var fields = {
				action: cfg.exportAction,
				kind: kind,
				start: state.start,
				weeks: String( state.weeks ),
				template: state.template,
				overrides: JSON.stringify( state.overrides )
			};
			if ( cfg.exportNonce ) { fields._wpnonce = cfg.exportNonce; }
			Object.keys( fields ).forEach( function ( name ) {
				var input = document.createElement( 'input' );
				input.type = 'hidden';
				input.name = name;
				input.value = fields[ name ];
				form.appendChild( input );
			} );
			document.body.appendChild( form );
			form.submit();
			document.body.removeChild( form );
			say( cfg.i18n.preparing );
			setTimeout( function () { say( '' ); }, 4000 );
		}

		// --- WhatsApp -------------------------------------------------------

		function showWhatsApp() {
			ui.wa.hidden = false;
			ui.waStatus.textContent = '';
			ui.waText.value = '';
			ui.waOpen.hidden = true;
			setBusy( true, cfg.i18n.buildingText );
			api( '/whatsapp', payload() ).then( function ( data ) {
				setBusy( false );
				ui.waText.value = data.text || '';
				if ( ui.waText.value ) {
					ui.waOpen.hidden = false;
					ui.waOpen.href = 'https://wa.me/?text=' + encodeURIComponent( ui.waText.value );
				}
				ui.waText.scrollTop = 0;   // show the top of the message, don't grab focus
				ui.wa.scrollIntoView( { block: 'nearest', behavior: 'smooth' } );
			} ).catch( function ( e ) {
				setBusy( false );
				ui.waStatus.textContent = ( 429 === e.status ? cfg.i18n.throttled : cfg.i18n.textFailed ) + ' ' + e.message;
			} );
		}

		function copyWhatsApp() {
			var text = ui.waText.value;
			if ( ! text ) { return; }
			var done = function () {
				ui.waStatus.textContent = cfg.i18n.copied;
				setTimeout( function () { ui.waStatus.textContent = ''; }, 2500 );
			};
			var fallback = function () {
				ui.waText.select();
				try { document.execCommand( 'copy' ); } catch ( e ) { /* nothing else to try */ }
				done();
			};
			if ( navigator.clipboard && navigator.clipboard.writeText ) {
				navigator.clipboard.writeText( text ).then( done, fallback );
			} else {
				fallback();
			}
		}

		// --- wiring ---------------------------------------------------------

		function moveWeek( delta ) {
			state.start = addDays( state.start, delta * 7 );
			syncControls();
			refresh( state.editing );
		}

		ui.start.addEventListener( 'change', function () {
			var picked = sundayOf( ui.start.value );
			if ( ! picked ) { ui.start.value = state.start; return; }
			state.start = picked;
			syncControls();
			refresh( state.editing );
		} );

		qa( '[data-nav]' ).forEach( function ( b ) {
			b.addEventListener( 'click', function () { moveWeek( parseInt( b.dataset.nav, 10 ) ); } );
		} );

		q( '[data-role="today"]' ).addEventListener( 'click', function () {
			state.start = currentSunday();
			syncControls();
			refresh( state.editing );
		} );

		qa( '[data-weeks]' ).forEach( function ( b ) {
			b.addEventListener( 'click', function () {
				state.weeks = parseInt( b.dataset.weeks, 10 ) || 1;
				syncControls();
				refresh( state.editing );
			} );
		} );

		qa( '[data-style]' ).forEach( function ( b ) {
			b.addEventListener( 'click', function () {
				if ( b.dataset.style === state.template ) { return; }
				state.template = b.dataset.style;
				syncControls();
				refresh( false );
			} );
		} );

		ui.editToggle.addEventListener( 'click', function () { setEditing( ! state.editing ); } );

		ui.reset.addEventListener( 'click', function () {
			if ( ! hasEdits() ) { return; }
			if ( ! window.confirm( cfg.i18n.confirmReset ) ) { return; }
			state.overrides = { lines: {}, notes: {} };
			state.originalNotes = {};
			state.hiddenLines = {};
			refresh( state.editing );
		} );

		qa( '[data-export]' ).forEach( function ( b ) {
			b.addEventListener( 'click', function () { download( b.dataset.export ); } );
		} );

		q( '[data-role="wa-show"]' ).addEventListener( 'click', showWhatsApp );
		q( '[data-role="wa-copy"]' ).addEventListener( 'click', copyWhatsApp );
		q( '[data-role="wa-close"]' ).addEventListener( 'click', function () { ui.wa.hidden = true; } );

		qa( '[data-zoom]' ).forEach( function ( b ) {
			b.addEventListener( 'click', function () {
				var step = b.dataset.zoom;
				if ( 'fit' === step ) {
					state.zoom.mode = 'fit';
				} else {
					state.zoom.mode = 'manual';
					state.zoom.scale = Math.max( 0.4, Math.min( 2, scale() + ( '+' === step ? 0.1 : -0.1 ) ) );
				}
				fit();
			} );
		} );

		var fitTimer = null;
		window.addEventListener( 'resize', function () {
			clearTimeout( fitTimer );
			fitTimer = setTimeout( fit, 150 );
		} );

		root.addEventListener( 'keydown', function ( e ) {
			if ( 'Escape' === e.key && ! ui.wa.hidden ) { ui.wa.hidden = true; }
		} );

		syncControls();
		refresh( false );
	}

	function start() {
		var tags = document.querySelectorAll( 'script.ttcc-gen-config' );
		Array.prototype.forEach.call( tags, function ( tag ) {
			if ( tag.dataset.ttccBooted ) { return; }
			tag.dataset.ttccBooted = '1';
			var cfg;
			try { cfg = JSON.parse( tag.textContent ); } catch ( e ) { return; }
			var root = document.getElementById( cfg.id );
			if ( root ) { boot( root, cfg ); }
		} );
	}

	if ( 'loading' === document.readyState ) {
		document.addEventListener( 'DOMContentLoaded', start );
	} else {
		start();
	}
} )();
