# Special-day automation catalog (proposed rules)

**What this is.** A proposed rule set for auto-generating the "special day" lines,
notes and decorations that Tzemach Tzedek Community Centre (Bondi, Chabad) adds to
its weekly timesheets. Each rule below was reverse-engineered from 478 irregular
items mined from 3+ years of historical sheets (5782–5786). Every printed *time*
was cross-referenced against the shul's zmanim engine; where the offset from a
zman is consistent across instances (within ±3 min, allowing for the sheet's
rounding), the rule is expressed as a **zman anchor** (e.g. "shkia − 25 min").
Where the printed value is stable regardless of the zman, the rule says **fixed**.

**Conventions used below.**
- Zman-derived *deadlines/markers* (shkia, tzeis, candles, chatzos, alos) are printed
  **to the minute**. *Minyan* times (Mincha, Maariv, Shacharis, Megillah) are
  generally **rounded to the nearest 5 min**.
- Sydney is Southern Hemisphere: winter fasts end early (~5:30–6:20 pm), summer
  fasts end late (~7:56–8:40 pm). A single anchor that holds across both seasons is
  therefore strong evidence; several rules below are validated across a >3-hour
  seasonal swing.
- **Every auto-generated line is a proposal only** — the generator should render
  each line as editable and removable per sheet, because the corpus shows the shul
  routinely hand-tunes wording, adds sponsor dedications, and overrides times.

Anchor abbreviations: `alos` (dawn), `netz` (sunrise), `misheyakir`, `sof_shema`,
`sof_tfila`, `solar_noon`, `mincha_gedola`, `plag`, `shkia` (sunset), `candles`
(=shkia−18), `tzeis` (nightfall ≈ shkia+25), `tzeis_shabbos` (≈ shkia+37/39),
`chatzos_layla` (halachic midnight).

---

## 1. Minor fasts (Tzom Gedalia, 10 Teves, Taanis Esther, 17 Tammuz)

Instances in corpus: 17 Tammuz (5782 nidche→Sun, 5786 Thurs), 10 Teves (5783, 5785
fell Fri, 5786), Taanis Esther (5784, 5785, 5786 — see also §3), Tzom Gedaliah
(5785 nidche→Sun, 5786 Thurs), Taanis Bechorim (see §4).

### Rule 1a — Fast start marker
- **Trigger**: any minor fast day.
- **Emits**: "Fast starts at HH:MM" (or "Alos Hashachar (Fast begins)"). **Time = alos hashachar (offset 0, print to the minute).**
- **Evidence**:

| date | printed start | anchor | sheet |
|---|---|---|---|
| 2022-07-17 (17 Tammuz nidche) | 5:34am | alos −1 (05:35) | 5782 wk46-49 |
| 2023-01-03 (10 Teves) | 4:12am | alos −1 (04:13) | 5783 wk13-15 |
| 2024-03-21 (Taanis Esther) | 5:41am | alos +0 (05:41) | Purim Notes 5784 |
| 2025-01-10 (10 Teves) | 4:20am | alos −1 (04:21) | 5785 wk15 |
| 2025-09-25 (Tzom Gedaliah) | 4:22am | alos −1 (04:23) | 5786 Tishrei |
| 2026-03-02 (Taanis Esther) | 5:23am | alos +0 (05:23) | Purim times 5786 |
| 2026-07-02 (17 Tammuz) | 5:37am | alos +0 (05:37) | wk41-44 v2 |
- **Confidence**: **HIGH** (8+ instances, all alos 0/−1, across summer & winter).

### Rule 1b — Fast end marker
- **Trigger**: any minor fast day.
- **Emits**: "Fast ends HH:MM" / "Maariv and end of Fast". **Time = tzeis (offset 0, to the minute).**
- **Evidence**: 17 Tammuz 5782 5:33pm = tzeis+0; Taanis Esther 5784 7:30pm = tzeis+0; 5785 7:42pm = tzeis+1; 5786 7:56pm = tzeis+0; 10 Teves 5783 8:39pm = tzeis+0; 5785 8:39pm = tzeis+1; 5786 8:38pm = tzeis+0; Tzom Gedaliah 5785/5786 6:19pm = tzeis+1.
- **Confidence**: **HIGH** (8+ instances, always tzeis 0/+1).

### Rule 1c — Fast-day afternoon Mincha (earlier than the rest of the week)
- **Trigger**: minor fast day (weekday). Mincha is pulled earlier to fit the fast-day Torah reading + Aneinu.
- **Emits**: fast-day Mincha line. **Time ≈ shkia − 25 min (rounded to 5).**
- **Evidence**:

| date | fast Mincha | week's shkia | offset | sheet |
|---|---|---|---|---|
| 2023-01-03 (10 Teves) | 7:45pm | 8:10pm | −25 | 5783 wk13-15 |
| 2025-12-30 (10 Teves) | 7:45pm | 8:09pm | −24 | 5786 wk14-16 |
| 2024-03-21 (Taanis Esther) | 6:40pm | 7:05pm | −25 | Purim Notes 5784 |
| 2025-03-13 (Taanis Esther) | 6:50pm | 7:16pm | −26 | 5785 wk23-25 |
| 2026-03-02 (Taanis Esther) | 7:00pm | 7:31pm | −31 | Purim times 5786 |
- **Confidence**: **HIGH** for 10 Teves (−24/−25); **MEDIUM** for Taanis Esther (−25 to −31; the 5786 −31 is an outlier — see open question).
- **Open question**: is fast-Mincha meant to be a fixed clock offset before shkia, or "the regular weekday Mincha, moved ~15 min earlier"? The regular Mon–Thurs Mincha is itself ~shkia−10, so the fast pulls it ~15 more.

### Rule 1d — Nidche (postponed) variant
- **Trigger**: fast's calendar date falls on Shabbos → observed the next day (Sunday). Applies to 17 Tammuz 5782 (→ Sun 17 Jul) and Tzom Gedaliah 5785 (3 Tishrei on Shabbos → Sun 6 Oct).
- **Emits**: header "Postponed Fast of …"; and the **Sunday Mincha/Maariv split** from the uniform week (Sun differs, Mon–Thurs normal). E.g. 5782: "Mincha … Sun 4:40pm, Mon–Thurs 4:55pm"; "Maariv … Sun 5:33pm, followed by refreshments; Mon–Thurs 5:35pm".
- **Confidence**: **HIGH** (2 instances). Note Tzom Gedaliah is *always* liable to be nidche when it lands on Shabbos.

### Rule 1e — Fall-on-Friday variant (10 Teves)
- **Trigger**: fast falls on Erev Shabbos (10 Teves 5785, Fri 10 Jan).
- **Emits**: notes "No early minyanim for Erev Shabbos" (fast runs to tzeis, little benefit to early Shabbos); "Mincha … earlier than usual and includes Kerias Hatorah"; Erev-Shabbos Mincha = **7:45pm** (that week shkia 8:10 → shkia−25, same as Rule 1c) "including Kerias Hatorah, but no Tachanun or Avinu Malkenu".
- **Confidence**: **MEDIUM** (1 instance, but internally consistent with 1c).
- **Open question**: 10 Teves is the only fast that can never be nidche (it can fall on Friday but is still observed that day) — confirm the shul wants the "no early minyan" note auto-emitted whenever 10 Teves = Friday.

### Rule 1f — Fast-day liturgy notes (no time)
- **Trigger**: any minor fast.
- **Emits** (standing text, reusable verbatim): "Shliach Tzibur says Aneinu…"; "Tachanun, Selichos and Avinu Malkeinu are recited"; on Taanis Esther Mincha, "We do not say Tachanun or Avinu Malkeinu at Minchah, because it is Erev Purim."
- **Confidence**: **HIGH** (recurs 5784/5785).

---

## 2. Tisha B'Av and the Nine Days

Two full instances: **5782** (9 Av on Shabbos → fast nidche to 10 Av/Sun) and **5786**
(9 Av weekday: Wed night → Thurs). Plus standalone halachic guides ("5782 Nine Days
and Fast day.txt", "5786 The Nine Days.txt").

### Rule 2a — Nine Days begin (Rosh Chodesh Av)
- **Trigger**: Rosh Chodesh Av.
- **Emits** note: "When Av enters, we reduce our joy…" (Luach Colel Chabad); + standing restriction notes (no laundry, no meat/wine except Shabbos/seudas mitzvah, daily siyum from RC through 15 Av). Verbatim blocks available in both guides.
- **Confidence**: **HIGH**.

### Rule 2b — Erev Tisha B'Av restrictions from Chatzos
- **Trigger**: Erev 9 Av (weekday) OR Shabbos Chazon when 9 Av = Shabbos.
- **Emits**: "From Chatzot Hayom (HH:MM) … study only Eichah, Iyov, unfavourable prophecies in Yirmeyahu, Midrash Eichah, Gittin 55b." **Time = chatzos = solar_noon (offset 0/−1).** (5782: 12:01pm = solar_noon+0; 5786: 12:01pm = solar_noon−1.)
- **Confidence**: **HIGH** (2 yrs).

### Rule 2c — Seudah hamafsekes / eating cutoff = Shkia
- **Trigger**: Erev 9 Av.
- **Emits**: seudah-hamafsekes note (egg in ashes; no two cooked dishes; no alcohol) + "Eating & drinking must stop by Shkia HH:MM". **Time = shkia (offset 0).** 5782: 5:19pm = shkia+0; 5786: 5:09pm = shkia+0.
- **Confidence**: **HIGH**.

### Rule 2d — Start-of-fast / footwear change
- **Trigger**: 9 Av begins.
- **Emits**: weekday: at Shkia remove leather shoes (5786 5:09pm = shkia+0). Shabbos variant: "Motzaei Shabbos 9 Av, say Baruch hamavdil…" **= tzeis_shabbos (5782 5:58pm = tzeis_shabbos+0).**
- **Confidence**: **HIGH**.

### Rule 2e — Maariv, Eicha & Kinos (night)
- **Trigger**: night of 9 Av.
- **Emits**: "Maariv, Megillas Eicha, Kinos" + decorations: sit on low chairs/cushions (BYO — shul furniture unavailable); borei me'orei ha'esh over a flame, no Havdalah.
- **Time**: weekday 5786 = with Maariv 5:37pm (= tzeis+1). Shabbos-motzaei 5782 = **6:45pm = tzeis_shabbos+47** (delayed so Shabbos fully ends before writing/Kinos). Add "Siyum" to the line in the Shabbos case (5782 line reads "Maariv, Megillas Eicha, Kinos, Siyum").
- **Confidence**: **HIGH** for the decoration set; **MEDIUM** for the night time (weekday follows Maariv=tzeis; motzaei-Shabbos is a fixed ~+45–47 delay, 1 instance).

### Rule 2f — Fast-day Shacharis + Kinos
- **Trigger**: 9 Av morning.
- **Emits**: "Shacharis, then Kinos (no tallis or tefillin; no tachanun)". Decorations: low chairs; each person reads Eichah individually; Kinos after Haftorah.
- **Time = fixed** (not zman-anchored): 5782 = **9:00am** (single minyan); 5786 = **8:00am & 9:30am** (two minyanim, 2nd "followed by Kinos"). Note the later 9:00/9:30 vs a normal 6:15/7:30 weekday — Tisha B'Av gets late morning minyanim.
- **Confidence**: **HIGH** that it is a fixed late-morning time; **MEDIUM** on the exact value (differs 9:00 vs 8:00+9:30 between the two years).

### Rule 2g — Chatzos, midday Mincha (Mincha Gedola) & tallis/tefillin resume
- **Trigger**: 9 Av afternoon.
- **Emits**: "Chatzot Hayom (earliest tallis & tefillin) HH:MM" = **solar_noon** (12:01). Then "Mincha (starting with korbonos)" at **Mincha Gedola = mincha_gedola − 2** (5782: 12:29pm vs mincha_gedola 12:31). Note "after Chatzos + Kinos we may sit on regular chairs."
- **Confidence**: **HIGH** (chatzos, mincha gedola both tight).

### Rule 2h — Afternoon Mincha on the fast day
- **Trigger**: 9 Av afternoon (the "main" Mincha before the fast ends).
- **Emits**: afternoon Mincha. 5782 = 4:55pm (that week shkia 5:20 → shkia−25); 5786 Thurs = 4:40pm (week's Sun–Wed evening baseline was ~4:57, fast-day pulled to 4:40). The 5786 fast-day line lists **"Thurs. 12:30pm & 4:40pm"** (midday Mincha Gedola shown as 12:30, then 4:40 afternoon).
- **Time ≈ shkia − 25 (rounded 5)**, same family as Rule 1c.
- **Confidence**: **MEDIUM** (2 instances, values consistent with the fast-Mincha family).

### Rule 2i — End of fast + Kiddush Levana
- **Trigger**: 9 Av ends.
- **Emits**: "End of Fast, Maariv, refreshments" = **tzeis** (5782 5:46pm = tzeis+0; 5786 5:37pm = tzeis+1). After Maariv, Rabbeinu Tam tefillin; Havdalah on wine (no candle/spices, nidche year); **Kiddush Levanah**.
- **Confidence**: **HIGH**.

### Rule 2j — Break-fast refreshments (sponsored, recurring dedication)
- **Trigger**: motzaei 9 Av (after Maariv).
- **Emits**: "Breaking the fast of Tisha b'Av: Refreshments at Tzemach Tzedek after Maariv" + **Gunsberger family dedication** (recurs verbatim in both 5782 and 5786: in honour of family who perished al kiddush Hashem, and Gershon's alte-zeida Yisroel ben Avraham Kalman haLevi whose yahrzeit is on Tisha b'Av).
- **Confidence**: **HIGH** (identical sponsor 2 yrs) — but flag the sponsorship for annual reconfirmation.

### Rule 2k — Nightly Siyum through 15 Av
- **Trigger**: Nine Days.
- **Emits**: "Nightly Siyum: Until 15 Menachem Av, a siyum each night after Maariv." **Time = after Maariv (relative).**
- **Confidence**: **HIGH**.

### Rule 2l — Meat/wine restriction lifts after chatzos 10 Av
- **Trigger**: 10 Av morning (weekday year) / 11 Av morning (when fast was nidche to 10 Av).
- **Emits**: "No meat or wine until after Chatzot Hayom on 10 Av (HH:MM)" (5786) OR "…until the morning of 11 Av" (5782 nidche). **Anchor chatzos = solar_noon** in the weekday case.
- **Confidence**: **HIGH** (note the date shifts by one when nidche).

### Rule 2m — Shabbos Chazon / Shabbos Nachamu labels
- **Trigger**: Shabbos before / after 9 Av.
- **Emits**: header "Shabbos kodesh: Devarim, Chazon" and "…Va'eschanan, Nachamu". Chazon extras: Alter Rebbe wore full Shabbos clothing; Pirkei Avos ch. 2 after Mincha; meat/wine allowed at seudah shlishis "but do not feast with company".
- **Confidence**: **HIGH**.

---

## 3. Purim season

Instances: 5783 (Purim Tues, after Shabbos Zachor), 5784 (Purim starts motzaei
Shabbos; Taanis Esther advanced to Thurs 11 Adar), 5785 (Purim on **Friday**), 5786
(Purim Tues). Rich "Purim Notes"/"Purim minhagim" documents in 5784, 5785, 5786.

### Rule 3a — Pre-Purim Shabbos labels
- **Trigger**: the four parshios + Mevorchim.
- **Emits** headers: "…Shekalim" (Shabbos Mevorchim Adar), "…Zachor" (Shabbos before Purim), "…Parah", "…HaChodesh" (Shabbos Mevorchim Nisan). Purim Katan / Shushan Purim Katan on 14/15 Adar I in a leap year (5784).
- **Confidence**: **HIGH** (labels recur every year, purely calendar-driven).

### Rule 3b — Shabbos Zachor extras
- **Trigger**: Shabbos Zachor.
- **Emits**: note "everyone — men, women, children — in shul to hear Zachor, ~11:30am"; Kiddush/farbrengen after Musaf. When Purim night follows immediately (Zachor Shabbos = Erev Purim), **early Shabbos Mincha** (5784: 1:30pm = mincha_gedola−2; kiddush/short farbrengen first).
- **Confidence**: **MEDIUM** (Zachor time 11:30 fixed, 1–2 instances).

### Rule 3c — Taanis Esther (link to §1)
- **Trigger**: Taanis Esther (13 Adar; advanced to Thurs 11 Adar when 13 Adar = Shabbos, as 5784).
- **Emits**: fast start = alos, end = tzeis (Rules 1a/1b); **Machatzis Hashekel before Mincha** (give three 50-cent coins); fast-day Mincha earlier (Rule 1c); "fast until after Maariv & Megillah, but if weak may eat < kezayis before Megillah."
- **Confidence**: **HIGH**.

### Rule 3d — Machatzis Hashekel
- **Trigger**: Taanis Esther, before Mincha.
- **Emits**: note (three coins, each half the local currency; in Australia three 50-cent coins) + "Tzemach Tzedek will have suitable coins available before Mincha (HH:MM)". Time tracks the fast-day Mincha (Rule 1c).
- **Confidence**: **HIGH** (5784/5785/5786).

### Rule 3e — Megillah, night reading
- **Trigger**: Purim night (after Maariv at tzeis).
- **Emits**: "Maariv HH:MM; Megillah reading ~HH:MM (SHARP); refreshments after." **Megillah ≈ Maariv + 15 min ≈ tzeis + 15 (round 5).**
- **Evidence**:

| year | Maariv (=tzeis) | Megillah night | gap |
|---|---|---|---|
| 5783 | 7:53pm | 8:05pm | +12 |
| 5784 | 8:10pm | ~8:25pm | +15 |
| 5785 | 7:42pm (tzeis+1) | 7:55pm | +13 |
| 5786 | 7:56pm (tzeis+0) | 8:15pm | +19 |
- **Confidence**: **MEDIUM** (consistent "shortly after Maariv"; exact gap 12–19 min). Decorations: three brochos (al mikrah Megillah, she'asah nissim, Shehecheyanu — Shehecheyanu at Shacharis also covers mishloach manos/matanos/seudah); no microphone; children encouraged; a small festive seudah at night (some avoid meat).

### Rule 3f — Megillah, day reading + Purim Shacharis
- **Trigger**: Purim day.
- **Emits**: two Shacharis minyanim then "Megillah 30 mins later" (or explicit ~+40 min): typically **6:05/6:15am & 7:00am**, Megillah **6:35/6:45am & 7:30am**. These cluster around netz (sunrise ~6:44–6:53): early Shacharis ≈ misheyakir+7, late ≈ netz+7..+16. Values are near-**fixed** year to year (6:05/6:15 & 7:00; Megillah +30–40).
- **Confidence**: **HIGH** (5783/5784/5785/5786 all match closely).
- **Open question**: 6:05am vs 6:15am first-minyan — 6:05 appears when Purim is Tues (5783/5786), 6:15 when Friday (5785). Confirm the driver.

### Rule 3g — Mishloach Manos / Matanos L'Evyonim / Seudah
- **Trigger**: Purim day.
- **Emits** standing notes: mishloach manos (2 foods, 1 person, same gender; "Purim Donation Cards" available at TT); matanos l'evyonim (2 poor people, ≥ a peruta ≈ 20c; via **Dovid Krinsky at Krinsky's Kosher Grocery** — recurring contact); Purim seudah "eat the main part before Shkia (HH:MM)". **Seudah deadline anchor = shkia** (5784: 7:01pm = shkia+0).
- **Confidence**: **HIGH**.

### Rule 3h — Purim-on-Friday variant (5785)
- **Trigger**: Purim day = Friday.
- **Emits**: "seudah much earlier — before Chatzos HaYom (HH:MM = solar_noon), in honour of Shabbos; if delayed, until the 10th halachic hour (HH:MM); further delay until Shabbos, least desirable." (5785: 1:04pm = solar_noon+0; 10th hour 4:09pm.) Also **early Mincha shifted earlier than usual** (5785 early minyan Mincha 3:00pm) and Erev-Shabbos Kabbolas Shabbos/Maariv per the normal early+regular split.
- **Confidence**: **MEDIUM** (1 instance, but halachically deterministic — recurs whenever Purim = Fri).

### Rule 3i — Shushan Purim (15 Adar)
- **Trigger**: 15 Adar.
- **Emits**: "No tachanun"; "add slightly to joy at the meals"; when Shushan Purim = Shabbos (5785), "no Av Harachamim after leining, no Tzidkascha Tzedek at Mincha" + Rebbe's guidance to "make up" on Shushan Purim within a Shabbos context. Sof Zeman Kiddush Levana for Adar note (computed, Jerusalem→Sydney).
- **Confidence**: **HIGH**.

### Rule 3j — Purim-day Mincha/Maariv split in the weekly grid
- **Trigger**: Purim week weekday grid.
- **Emits**: the irregular per-day split, e.g. 5786 "Mincha … Sun/Wed/Thurs 7:17pm; Mon 7:00pm (Taanis Esther); Tues 4:30pm (Purim)"; "Maariv … most days 7:58pm; Tues 8:30pm". Tues (Purim) Mincha **4:30pm is fixed** across 5783/5786 (much earlier, to free the day for seudah).
- **Confidence**: **HIGH** (Tues 4:30 Mincha identical 5783 & 5786).

---

## 4. Pesach

Full schedule in "5786 times -wk 28b.txt"; partial in "5785 times -wk 26 to 28.txt".

### Rule 4a — Shabbos HaGadol
- **Trigger**: Shabbos before Pesach.
- **Emits**: header "…HaGadol"; **Shabbos HaGadol derosha before leining**; kiddush/farbrengen (5786 also "in honour of the Rebbe's birthday"); **Mincha + Haggadah (Avadim Hayinu…) + Seder Nigunim** (5786 6:30pm = shkia−26; 5785 combined with pre-Seder shiur line). When Erev Pesach = Shabbos (5785), also chometz deadlines fall on Shabbos.
- **Confidence**: **HIGH** (derosha + Haggadah line both years).

### Rule 4b — Bedikas Chometz
- **Trigger**: night before Erev Pesach.
- **Emits**: "Bedikas Chometz, not before HH:MM, then first Kol Chamira." **Anchor = tzeis (offset 0).** 5785: 6:04pm = tzeis+0; 5786: 7:17pm = tzeis+0.
- **Confidence**: **HIGH**.

### Rule 4c — Taanis Bechorim + Siyum
- **Trigger**: Erev Pesach morning (or Thurs when Erev Pesach = Shabbos).
- **Emits**: "Taanis Bechorim starts HH:MM" (= alos: 5785 4:56am = alos+0; 5786 5:49am = alos+0) + "each Shacharis followed by a siyum (exempts firstborns)".
- **Confidence**: **HIGH**.

### Rule 4d — Chometz deadlines (end of eating; biur/nullify)
- **Trigger**: Erev Pesach morning.
- **Emits**: "Finish eating chometz by HH:MM" = **sof_zman achilas chometz** (5786 11:00am = sof_tfila+0; 5785 10:01am = sof_tfila+0 — i.e. printed = engine's sof_tfila-derived eating deadline). "Finish burning/nullifying + 2nd Kol Chamira by HH:MM" ≈ sof_tfila+59 (5786 11:59am; 5785 10:58am). NOTE the engine's `sof_tfila` label here is being used as the achilas-chometz hour; biur ≈ +59 min later.
- **Confidence**: **HIGH** (both deadlines match within a minute across 2 yrs).
- **Open question**: confirm the engine exposes distinct "sof achilas chometz" and "sof biur chometz" zmanim; the corpus shows eating-deadline = printed sof_tfila value and biur = +~59 min.

### Rule 4e — Sha'a Asiris
- **Trigger**: Erev Pesach afternoon (and Erev Shavuos, Erev any Yom Tov seudah — see §6).
- **Emits**: "Sha'a asiris (from which not to over-eat before the Seder) HH:MM." 5786 = 3:55pm. (Engine had no candidate offset returned; this is the start of the 10th halachic hour.)
- **Confidence**: **LOW** on anchor (1 Pesach instance, engine gave no match); the zman is deterministic (10th proportional hour) so the engine should compute it directly rather than offset a listed anchor.

### Rule 4f — Sedarim: candle lighting, Mincha/Seder Korban Pesach, Maariv+Hallel, Afikomen
- **Trigger**: 1st night Pesach.
- **Emits**: candle lighting = **candles** (5786 6:33pm = candles+0); "Mincha & Seder Korban Pesach" ≈ candles+2; "Maariv (incl Hallel 1st & 2nd nights)" ≈ tzeis−1; "Finish eating Afikomen by chatzos = chatzos_layla" (5786 12:59am = chatzos_layla+0; 5785 11:56pm = chatzos_layla+0).
- **Confidence**: **HIGH** (candles, chatzos both tight).

### Rule 4g — 2nd-night candle rule (light only after tzeis)
- **Trigger**: 2nd night of any Yom Tov (Pesach, Succos, Shavuos, RH).
- **Emits**: "Candle lighting (Yom Tov) **not before HH:MM**" = **tzeis_shabbos** (the "not before" nightfall value). Pesach 5786: 7:26pm = tzeis_shabbos+0. This is the single most consistent cross-festival anchor (see also RH 2nd night, Succos 2nd night, Shmini Atzeres → Simchas Torah).
- **Confidence**: **HIGH** (holds across every festival in the corpus).

### Rule 4h — Chol Hamoed Pesach schedule
- **Trigger**: Chol Hamoed days.
- **Emits**: Shacharis 8:00am, 9:15am (public-holiday days) / weekday 6:15,7:30,9:15; Mincha ~5:30pm; Maariv ~6:10pm; Omer-count annotation on each Maariv line ("Days 3 & 4 of Omer"). Public-holiday overlap (Sun/Mon early-April) shifts Shacharis to the two-late-times pattern.
- **Confidence**: **MEDIUM** (1 full Pesach instance; overlaps §12 public-holiday rule).

### Rule 4i — Shvi'i shel Pesach night learning
- **Trigger**: night of 7th day.
- **Emits**: "All night learning after Seudas Yom Tov"; and next morning "Alos haShachar HH:MM" is printed (= alos+0, 5786 4:54am) tied to the all-night learners.
- **Confidence**: **MEDIUM** (1 instance).

### Rule 4j — Acharon shel Pesach: Yizkor + Seudas Moshiach
- **Trigger**: 8th day (Acharon).
- **Emits**: "Shacharis 10:00am (Yizkor approx 11:30am)"; "**Mincha followed by Seudas Moshiach**" (5786 4:55pm — Mincha moved earlier for the meal, ≈ plag+24 / shkia−45); Maariv & motzaei Yom Tov = tzeis.
- **Confidence**: **MEDIUM** (1 instance; Seudas Moshiach is a fixed Chabad custom).

### Rule 4k — Kinus Torah parts 1 & 2
- **Trigger**: last days of Pesach (also Succos — see §10).
- **Emits**: "Mincha followed by Kinus Torah pt 1" (7th-day eve) and "pt 2" (following day). 5786: pt1 Fri 6:35pm, pt2 Sat 6:30pm. Anchored to that day's Mincha (~candles+3).
- **Confidence**: **MEDIUM** (parts 1&2 pattern also appears in Succos — Kinus Torah is a recurring 2-part fixture).

### Rule 4l — Isru Chag, Omer start, Sotah shiur
- **Trigger**: after Pesach.
- **Emits**: "Isru Chag" day header; "Maariv followed by the first counting of the Omer" on 1st night (2nd night of Pesach); Sefirah-day annotation on subsequent Maariv lines ("Sefirah 9"); "After Maariv: start of shiurim in Maseches Sotah — one daf per night."
- **Confidence**: **HIGH** for Isru Chag/Omer start; **MEDIUM** for Sotah shiur (1 instance).

---

## 5. Sefirah / Lag B'Omer / Pesach Sheni

### Rule 5a — Sefirah day annotation
- **Trigger**: each day during the Omer.
- **Emits**: "(Sefirah N)" appended to the Maariv/Kabbolas-Shabbos line. Correct instances: 5786 "Sefirah 9" (10 Apr, day after Pesach). **Anchor = none (label, count of the day).**
- **Confidence**: **HIGH** (mechanically the day-count from 16 Nisan).
- **Open question / suspected error**: 5785 wk26-28 shows "(Sefirah 20)" on 29 Adar and "(Sefirah 27)" on 7 Nisan — **both before Pesach**, so they cannot be real Omer counts (see Suspected Errors). Likely a leftover template label. The generator must gate Sefirah labels to 16 Nisan–5 Sivan only.

### Rule 5b — Pesach Sheni
- **Trigger**: 14 Iyar.
- **Emits**: "Pesach Sheni: 14 Iyar (Thurs night & Fri daytime). No Tachanun."
- **Confidence**: **HIGH** (deterministic; 1 corpus instance).

### Rule 5c — Lag B'Omer
- **Trigger**: 18 Iyar.
- **Emits**: "Lag b'Omer: 18 Iyar (Mon night & Tues). Special events TBA. No Tachanun."
- **Confidence**: **HIGH** (1 instance; deterministic).

---

## 6. Shavuos

Full instance: "5786 times -wk 34 to 36 incl Shavuos.txt".

### Rule 6a — Erev Shavuos: Eruv Tavshilin + Sha'a Asiris
- **Emits**: "Remember to make an Eruv Tavshilin on Thurs"; "Sha'a Asiris (do not over-eat before the Yom Tov seudah) HH:MM" (5786 2:25pm; engine gave no offset — compute 10th hour directly, cf. Rule 4e). Candle lighting = **candles** (4:41pm = candles+0); Erev Mincha ≈ candles+9.
- **Confidence**: **HIGH** for eruv/candles; **LOW** for Sha'a Asiris anchor.

### Rule 6b — Tikkun Leil Shavuos
- **Trigger**: 1st night.
- **Emits**: promotional box "Tikkun Leil Shavuos: All-night learning, 1st night… refreshments during the night… details TBA" + a schedule entry "Tikkun Leil Shavuos program … Details TBA". Also "No tachanun during the first twelve days of Sivan".
- **Confidence**: **HIGH**.

### Rule 6c — 1st day: Aseres Hadibros + ice-cream party
- **Trigger**: 1st day Shavuos.
- **Emits**: "Shacharis 10:00am (Aseres Hadibros approx 11:15am)" + footnote "Bring children to shul to hear the reading; after the leining, an ice-cream party for children." Print Alos hashachar (5:23am = alos+0) for the all-night learners.
- **Confidence**: **HIGH**.

### Rule 6d — Yizkor (2nd day)
- **Emits**: "Shacharis 10:00am (Yizkor approx 11:30am)".
- **Confidence**: **HIGH**.

### Rule 6e — 2nd-day farbrengen with early Mincha
- **Trigger**: 2nd day Shavuos afternoon.
- **Emits**: "Mincha (followed by farbrengen) HH:MM" moved **earlier than usual** (5786 4:20pm = candles−20/shkia−38) + footnote "Farbrengen … with washing, to see out the Yom Tov. Hence the early start for Mincha." Motzaei: "Motzaei Shabbos, Motzaei Yom Tov, Maariv" = tzeis_shabbos (5786 5:38pm = +0).
- **Confidence**: **MEDIUM** (1 instance; mirrors the 2nd-day-YT farbrengen pattern seen at Shmini Atzeres/Gimmel Tammuz).

### Rule 6f — Isru Chag
- **Emits**: "(8 Sivan: Isru Chag)" note on the following week's grid. **Kinus Torah**: not present in the Shavuos sheet (see Coverage gaps).
- **Confidence**: **HIGH** for Isru Chag.

---

## 7. Gimmel Tammuz + chassidic dates

### Rule 7a — Gimmel Tammuz (Rebbe's yahrzeit, 3 Tammuz)
- **Trigger**: 3 Tammuz + the Shabbos before.
- **Emits**: "Extra readings of Torah parsha for the Shabbos before 3 Tammuz"; special farbrengen ("Details TBA" / with guest e.g. Rabbi Ari Shishler); special Chassidus shiur 9:15am (5782); when 3 Tammuz on/near Shabbos, **early Mincha + Pirkei Avos ch. 4** (5784 12:25pm = mincha_gedola−5) then "Farbrengen re Gimmel Tammuz after Mincha".
- **Confidence**: **HIGH** (3+ yrs: 5782, 5784, 5786).

### Rule 7b — 12–13 Tammuz (Chag HaGeulah, Frierdiker Rebbe)
- **Emits**: "12 & 13 Tammuz: Sun night to Tues evening. Chag HaGeulah of the Frierdiker Rebbe. Special events TBA."
- **Confidence**: **MEDIUM** (1 instance, 5782).

### Rule 7c — Yud Shevat (10 Shevat)
- **Emits**: header "…the Shabbos before Yud Shevat"; "Yud Shevat: special events TBA."
- **Confidence**: **HIGH** (5786; deterministic).

### Rule 7d — Yud-Alef Nisan (Rebbe's birthday)
- **Emits**: "Yud-alef Nisan: the Rebbe's birthday. Farbrengen Wed evening. Details TBA." (5785). Also flagged in 5786 Shabbos HaGadol farbrengen "in honour of the Rebbe's birthday".
- **Confidence**: **HIGH**.

### Rule 7e — 18 Elul (Baal Shem Tov & Alter Rebbe birthday)
- **Emits**: "18 Elul: birthday of the Baal Shem Tov & Alter Rebbe. Special events TBA."
- **Confidence**: **HIGH** (1 instance; deterministic).

### Rule 7f — Rosh Chodesh Kislev
- **Not present** in corpus as a distinct item (see Coverage gaps). Rosh Chodesh Kislev / Yud-Tes Kislev / Chag HaGeulah of the Alter Rebbe do not appear.
- **Confidence**: **N/A** — gap.

---

## 8. Elul/Selichos + Rosh Hashana

### Rule 8a — Rosh Chodesh Elul customs
- **Emits**: "First day of L'David Hashem Ori in Shacharis & Mincha; practise blowing shofar; from 2 Elul blow shofar daily + 3 extra Tehillim (Mon Tehillim 1–3, etc.)".
- **Confidence**: **HIGH** (1 instance; standing custom).

### Rule 8b — Weekday Selichos (Elul)
- **Trigger**: from the first Selichos through Erev RH.
- **Emits**: paired "Selichos HH:MM / Shacharis HH:MM" lines. Weekday: **Selichos 5:50am → Shacharis 6:15am; Selichos 7:00am → Shacharis 7:30am** (Selichos ≈ 25 min before each Shacharis; Shacharis ≈ netz+20). Last Sunday before Erev RH shifts to 7:30/8:00 & 8:45/9:15.
- **Confidence**: **HIGH** (weekday pattern consistent; ~25 min before Shacharis).

### Rule 8c — First Selichos (motzaei Shabbos) — farbrengen + goral
- **Trigger**: motzaei Shabbos of first Selichos.
- **Emits**: "Farbrengen leading up to Selichos" **11:00pm** (= chatzos_layla−51); "Selichos followed by Goral to the Rebbe" **11:50pm** (= chatzos_layla−1, i.e. just before halachic midnight); "For an entry in the Goral, contact Yitzchok Barber 0411 422 770."
- **Confidence**: **MEDIUM** (1 instance; Selichos anchored to just-before-chatzos-layla is meaningful).

### Rule 8d — Erev Rosh Hashana sequence
- **Emits**: Selichos 5:30/6:30 → Shacharis 6:15/7:30 (+ **Hatoras Nedarim after each Shacharis**); "Morning Shema finish by HH:MM" = sof_shema; **Eruv Tavshilin** reminder (when RH runs into Shabbos); "Mincha (the last one for the year) + Tehillim"; "Derosha before Maariv"; candle lighting ("Yom HaZikaron") = **candles**; Maariv = tzeis.
- Anchors: candle lighting 5:33pm = candles+0 (5785/5786 identical); Mincha 5:35pm = candles+2; Maariv 6:20/6:25pm = tzeis+1..+4.
- **Confidence**: **HIGH** (5785 & 5786 near-identical).

### Rule 8e — Rosh Hashana days 1 & 2
- **Emits**: "Morning Shema finish by HH:MM" (=sof_shema); Shacharis 9:00am ("Hodu…"); "Tekias Shofar approx 11:10am" (fixed); "Mincha, then Tashlich: after Musaf (Mincha Gedolah HH:MM) & 5:00pm"; day-1 2nd-night candle lighting "not before HH:MM" = **tzeis_shabbos** (Rule 4g); day-2 "Maariv & end of RH" = tzeis.
- Anchors: Tashlich Mincha Gedola = mincha_gedola+1/+2; afternoon 5:00pm = plag+21/shkia−52 (roughly fixed 5:00pm). 2nd night 6:29pm = tzeis_shabbos+0.
- **Confidence**: **HIGH** (2 yrs).

### Rule 8f — Tashlich
- **Trigger**: RH day 1 afternoon (day 2 if day 1 = Shabbos).
- **Emits**: "Tashlich" appended to the afternoon Mincha line (after Musaf & at 5:00pm).
- **Confidence**: **HIGH**.

---

## 9. Yom Kippur

Instances: 5785 (YK on Shabbos), 5786 (YK Thurs). Winter-to-summer swing shows the
anchors clearly.

### Rule 9a — Erev Yom Kippur sequence
- **Emits**: Shacharis 6:15/7:30/9:00 (extra late minyan); **Early Mincha followed by lekach** (5785 4:30pm; 5786 3:15pm — a *fixed-ish early afternoon* slot, both ≈ plag−60..−88, i.e. well before plag, driven by needing a full pre-fast meal); candle lighting ("Yom HaKippurim") = **candles** (5786 5:40pm = candles+0; 5785 6:47pm = candles+0); "Shkia: fast begins for men (tallis already on with brocha)" = **shkia** (5786 5:58pm = shkia+0; 5785 7:05pm = shkia+0); "Stand and say Ashamnu & Al Chet before Kol Nidrei"; **Kol Nidrei + Derosha** ≈ shkia+10..+12 (5785 7:15pm; 5786 6:10pm); "Maariv after the derosha".
- **Confidence**: **HIGH** for candles/shkia/Kol Nidrei; **MEDIUM** for the lekach-Mincha clock time (4:30 vs 3:15 differ; both "early").
- **Open question**: Early Mincha+lekach time swung from 4:30pm (5785, YK Shabbos) to 3:15pm (5786, YK Thurs) — is it a fixed clock time, a proportional-hour anchor, or set per year by the Rov?

### Rule 9b — Yom Kippur day
- **Emits**: "Morning Shema finish by HH:MM" (=sof_shema); Shacharis 9:30/10:00am ("Hodu…"); **Yizkor** approx 12:15–12:45pm (≈ mincha_gedola / solar_noon+3); Mincha + derosha (5786 3:45pm; 5785 5:00pm); **Neilah** (5786 5:20pm = shkia−38; 5785 6:20pm = shkia−46, ~40 min before shkia); "Maariv & end of Fast" = **tzeis_shabbos** (5786 6:36pm = +0; 5785 7:44pm = +0); then **Kiddush Levana & refreshments** after Maariv.
- Anchors: end of fast = tzeis_shabbos (note: uses the later tzeis, consistent both yrs); Neilah ≈ shkia−40 (round 5).
- **Confidence**: **HIGH** for Yizkor/end-of-fast; **MEDIUM** for Neilah offset (−38 vs −46).

---

## 10. Succos through Simchas Torah

Two full instances: 5785 Tishrei, 5786 Tishrei.

### Rule 10a — Erev Succos
- **Emits**: **Eruv Tavshilin** reminder; candle lighting = **candles** (5785 6:51pm; 5786 6:43pm, both +0); "Farbrengen each night of Sukkos. Venues & times TBA." Erev-YT Shacharis uses the two-late-times (Sunday-style) pattern even on a weekday (5786 Mon 8:00 & 9:15).
- **Confidence**: **HIGH**.

### Rule 10b — Succos days 1 & 2
- **Emits**: Shacharis 10:00am ("Kiddush in sukkah after Musaf"); "Mincha followed by **Kinus Torah part 1**" (day 1); day-1 2nd-night candle lighting "not before HH:MM" = **tzeis_shabbos** (Rule 4g); day-2 "Maariv & end of Yom Tov" = tzeis.
- **Confidence**: **HIGH**.

### Rule 10c — Chol Hamoed Succos (extra 9:15 Shacharis + public-holiday overlap)
- **Emits**: weekday Shacharis with **extra 9:15am minyan** (6:15, 7:30, 9:15); Shabbos Chol Hamoed "Mincha followed by **Kinus Torah part 2**". Public-holiday days push Shacharis to the two-late-times pattern.
- **Confidence**: **HIGH** (extra 9:15 minyan recurs across Chol Hamoed Succos both yrs).

### Rule 10d — Simchas Beis Hashoeva
- **Emits**: "Shule Simchas Beis Ha'shoevah: children's rally. Details TBA" (Chol Hamoed).
- **Confidence**: **HIGH** (2 yrs).

### Rule 10e — Hoshana Rabba
- **Emits**: "Tehillim, apple & honey (starting at chatzot ha'laila) HH:MM" = **chatzos_layla** (5785 12:40am = +1; 5786 12:42am = +1); Shacharis with Hoshanos (extra 9:15 minyan); **Eruv Tavshilin**; "Kiddush in sukkah, followed by Hakofos after Maariv"; "Farbrengen after Hakofos".
- **Confidence**: **HIGH**.

### Rule 10f — Shmini Atzeres (night hakofos / Geshem / Yizkor / children's program)
- **Emits**: Erev candle lighting = **candles**; "Kiddush in sukkah + Hakofos after Maariv" + "Farbrengen after Hakofos"; day: Shacharis 10:00am ("in Musaf change to Mashiv ha'ruach" = **Tefilas Geshem**); **Yizkor approx 11:45am**; "**Children's program including Hakofos 6:30pm–8:00pm**"; Mincha + **Tahalucha** (5785 7:05pm); night candle lighting for Simchas Torah "not before HH:MM" = **tzeis_shabbos**; "Maariv followed by Hakofos, Kiddush & farbrengen".
- **'Under the Stars' naming**: **not found** in the corpus. The evening "Children's program including Hakofos 6:30–8:00pm" is the likely referent but is not labelled "Under the Stars" (see Open questions).
- **Confidence**: **HIGH** for the components; naming open.

### Rule 10g — Simchas Torah day (Birchas Kohanim + hakafos)
- **Emits**: "Shacharis including **Birchas Kohanim** 10:00am"; "Kiddush, then Hakafos, Krias haTorah, Musaf approx 11:00am"; "Maariv & end of Yom Tov" = tzeis_shabbos.
- **Confidence**: **HIGH**.

### Rule 10h — Kinus Torah parts / Tahalucha
- **Emits**: Kinus Torah part 1 (Succos day 1 Mincha) and part 2 (Shabbos Chol Hamoed Mincha); Tahalucha after Shmini Atzeres Mincha.
- **Confidence**: **HIGH** for Kinus Torah (2 yrs); **MEDIUM** for Tahalucha (1 explicit instance).

### Rule 10i — Shabbos Bereishis / post-Yom-Tov resumption
- **Emits**: "Shabbos Bereishis / Mevorchim" header, farbrengen with washing + seder nigunim; note that the Erev-Shabbos early minyan resumes the following week.
- **Confidence**: **HIGH**.

---

## 11. Chanukah

Instances: 5783 (wk13-15), 5786 (wk11-16). Southern-Hemisphere summer Chanukah →
very late shkia (~8:00pm), which drives the unusual evening ordering.

### Rule 11a — Nightly home lighting anchor
- **Trigger**: each Chanukah night (Sun–Thurs).
- **Emits**: "Light at home from HH:MM" = **shkia** (offset 0..+3). 5783 8:06pm = shkia+2; last night 8:07pm = shkia+0; 5786 8:04pm = shkia+3; Nittel-night reference 8:07pm = shkia+0.
- **Confidence**: **HIGH**.

### Rule 11b — Shul lighting before weekday Mincha
- **Trigger**: Chanukah weekday.
- **Emits**: "Mincha and Chanukah candles in shule … Sun–Thurs HH:MM" — a **fixed early-evening slot ~6:25pm** (5786 6:25pm; 5783 combined-Mincha 6:30pm), well before the late summer shkia, with **Maariv delayed to ~9:00pm** to follow the home-lighting time.
- **Confidence**: **HIGH** (2 yrs; the "shul candles before Mincha, Maariv at 9pm" structure recurs).

### Rule 11c — Extra 9:00/9:15am Shacharis
- **Trigger**: Chanukah weekdays.
- **Emits**: extra late Shacharis added to the weekday grid (5783 "Also Mon–Fri 9:00am"; 5786 "Mon–Fri … 9:15am").
- **Confidence**: **HIGH** that it recurs; **rationale unstated** (see Open questions — likely Hallel / school groups).

### Rule 11d — Erev Shabbos Chanukah sequencing
- **Trigger**: Friday during Chanukah.
- **Emits (early minyan)**: "Chanukah candle lighting at home: not before HH:MM (=plag), followed by Shabbos lighting to be completed by approx 7:40pm"; Kabbolas Shabbos delayed to ~7:30pm. **(regular minyan)**: "Chanukah lighting not before HH:MM (=plag), but before Shabbos candle lighting at HH:MM (=candles)". Anchors: "not before" = **plag** (5783 6:40pm = plag+0; 5786 6:38pm = plag+0); regular Shabbos candles = **candles** (5786 7:46pm = candles+0).
- **Confidence**: **HIGH** (2 yrs, plag & candles both +0).

### Rule 11e — Single combined Erev-Shabbos Mincha variant
- **Trigger**: Erev Shabbos Chanukah (and/or Chanukah+Rosh Chodesh convergence).
- **Emits**: "Erev Shabbos Mincha (This is the only Mincha) HH:MM" — collapses the usual early/regular split into one (5783 6:30pm; 5786 6:28pm = plag−10).
- **Confidence**: **HIGH** (2 yrs).

### Rule 11f — Motzaei Shabbos lighting
- **Emits**: "Chanukah candles on Motzaei Shabbos — light at home after Havdalah" (relative, no time).
- **Confidence**: **HIGH**.

### Rule 11g — Last night
- **Emits**: "Sun night is the last night of lighting Chanukah candles. Light at home from HH:MM (=shkia)."
- **Confidence**: **HIGH**.

---

## 12. Calendar labels & misc

### Rule 12a — Chazak / siyum lines
- **Emits**: "Shabbos kodesh: <parsha>, Chazak" upon completing a Chumash (Bamidbar 5782, Bereishis 5785/5786, Shemos 5785). Purely calendar-driven.
- **Confidence**: **HIGH**.

### Rule 12b — Mevorchim / Shekalim / HaChodesh header labels
- **Emits**: append "Mevorchim", "Shekalim", "Zachor", "Parah", "HaChodesh", "Nachamu", "Chazon", "Shushan Purim" etc. to the Shabbos header per the luach. (See §2, §3.)
- **Confidence**: **HIGH**.

### Rule 12c — V'sein tal u'matar
- **Emits**: "Starting on Thurs 4/12 in Maariv, change to 'v'sein tal u'matar…'" — **fixed civil date 4/5 December** (Diaspora). 
- **Confidence**: **HIGH** (deterministic annual date).

### Rule 12d — Nittel Nacht
- **Trigger**: 24 Dec night (Chabad custom).
- **Emits**: "Nittel from HH:MM to HH:MM" = **shkia → chatzos_layla** (5786 8:07pm = shkia+0; end 12:55am = chatzos_layla+0).
- **Confidence**: **HIGH** for the anchors (1 instance but both exact).

### Rule 12e — Rosh Chodesh notes
- **Emits**: "When Adar enters, we increase our joy"; "When Av enters, we reduce our joy"; Nisan "Nasi / Y'hi Ratzon for the first 13 days"; Elul shofar/L'David (§8a).
- **Confidence**: **HIGH**.

### Rule 12f — No-Tachanun periods
- **Emits**: "No tachanun during the first twelve days of Sivan"; no-Tachanun flags on Shushan Purim, Pesach Sheni, Lag B'Omer, all of Nisan, Chanukah, etc.
- **Confidence**: **HIGH**.

### Rule 12g — Season-ending notes (early minyan / halacha shiur)
- **Emits**: "(The last one until after Tishrei 5786.)" on the final Erev-Shabbos early minyan and final Shabbos halacha shiur before winter; "This is the last Shabbos halacha shiur until after Sukkos 5787"; and resumption notes in Tishrei.
- **Confidence**: **HIGH** (recurs 5785 & 5786) — but the exact cutoff week is set by the shul, not obviously zman-derivable.
- **Open question**: what luach condition triggers the last early-minyan / halacha-shiur of the season? (Appears tied to clock-change / candle-lighting getting too early, but no explicit rule.)

### Rule 12h — Public-holiday interactions (Christmas / Boxing Day / New Year)
- **Trigger**: AU public holidays overlapping a week.
- **Emits**: Shacharis shifts to the two-late-times "Sunday pattern" on the holiday days (e.g. 5783 "Public holidays: Sun, Mon & Tues" → Sun–Tues 8:00 & 9:00; 5786 Christmas/Boxing/New-Year Thurs & Fri 8:00 & 9:15); Mincha/Maariv splits accordingly.
- **Confidence**: **HIGH** that a rule exists; **the holiday label is often NOT printed** — inferred from the calendar (see Open questions). Generator needs an AU-public-holiday calendar feed.

---

## Suspected sheet errors found

Every item whose `suspected_error` was non-null, plus the duplicate_diff:

1. **wk41-44 duplicate (the duplicate_diff finding)** — "5786 times -wk 41 to 44.txt" vs "…v2.txt" are byte-identical except (a) a cosmetic "SOURCE PDF:" header and (b) the Fast of 9 Av start time: non-v2 reads **"starts Wed. at 5:09am"**, v2 reads **"5:09pm"**. The "am" is a typo — a Tisha B'Av fast starts at sunset (that week's shkia 5:07–5:10pm), confirmed by the engine anchoring 5:09pm to shkia+0 vs 5:09am to alos−24. **Use v2; treat non-v2 as superseded.**
2. **Postponed 17 Tammuz Mincha split (5782)** — Sun 4:40pm differs from Mon–Thurs 4:55pm (fast day), not a uniform week. *(Expected, fast-driven.)*
3. **Chanukah extra 9:00am Shacharis (5783)** — added on top of the usual Mon–Fri 6:15/7:30; rationale unstated.
4. **Chanukah public-holiday Shacharis split (5783)** — Sun–Tues vs Wed–Fri, tied to an above-line "Public holidays" note.
5. **10 Teves public-holiday Shacharis split (5783)** — Sun & Mon vs Tues–Fri.
6. **10 Teves fast-day Mincha (5783)** — Tues 7:45pm earlier than the 7:59pm week.
7. **Shabbos Tetzaveh Mincha, no Seder Nigunim (5783)** — Purim-week header but no printed Megillah time; Seder Nigunim omitted.
8. **Fast of Esther / Purim Mincha & Maariv splits (5783, 5786)** — Mon/Tues diverge (fast + Purim).
9. **Purim day 4:30pm→8:30pm Mincha→Maariv gap (5786)** — unusually large gap; flagged as outlier, not clearly an error.
10. **Erev-RH "two Maariv times" (5785)** — 5:40pm (with Mincha) and 6:20pm separately on the same Sunday; likely early/late option, confirm.
11. **"Morning Shema finish by8:34am" (5785)** — missing space typo.
12. **"followed by Musaf)" stray parenthesis (5785 Succos day 2; 5786 Succos day 2)** — OCR/typo, no opening paren.
13. **"(Sefirah 20)" & "(Sefirah 27)" before Pesach (5785 wk26-28)** — impossible Omer counts before 16 Nisan; leftover/mistaken template label. **Gate Sefirah labels to the Omer window.**
14. **Extra 9:15am Friday Shacharis (5786 Tishrei, 3 Oct)** — third minyan on a non-YT/non-CH"M Friday; possible Aseret-Yemei-Teshuva anomaly.
15. **Erev-Succos Monday Shacharis 8:00 & 9:15 (5786)** — Sunday-pattern on a Monday (Erev YT); expected.
16. **Chanukah extra 9:15am Shacharis (5786)** — Chanukah connection inferred, reason not printed.
17. **Chanukah early-minyan Kabbolas Shabbos 7:30pm (5786)** — later than usual, driven by lighting order.
18. **"Sunda)y" typo (5786 wk04)** — OCR artifact for "Sunday)".
19. **Christmas/Boxing-Day Shacharis (5786 wk14-16)** — holiday schedule, no label printed.
20. **New Year's Day Shacharis (5786 wk14-16)** — holiday schedule, no label printed; also Mon–Wed/Fri drop the 6:15am with no stated reason, and the 10 Teves fast Tues isn't separately called out in that Shacharis line.
21. **"8:000am" typo (5786 Erev Shvi'i Pesach)** — extra zero for 8:00am.
22. **"8:15pm" Yud-Shevat-week Shacharis three-way split (5786 wk17-19)** — Sun/Mon, Tue/Wed, Thu/Fri groupings unlike the uniform pattern; tied to a Mon public holiday + Yud Shevat but no explicit rule.
23. **Shabbos Tetzaveh Purim header + no Megillah time (5786 wk23-25)** — header names Purim (Megillah) but Purim is the following week; likely mislabeled/leftover header.
24. **Shabbos Tetzaveh Mincha, no Seder Nigunim (5786 wk23-25)** — omits the usual "followed by Seder Nigunim".
25. **Extra 2:00pm weekday Mincha (5786 wk37-40)** — appears in the Gimmel Tammuz week *and persists the next week with no occasion stated*; unclear if standing minyan or copy-paste carryover (see Unexplained items).
26. **Motzaei-Shavuos combined-Maariv wording (5786)** — "Motzaei Shabbos, Motzaei Yom Tov, Maariv"; YT-specific phrasing, not an error.

---

## Unexplained items needing shul input

1. **Recurring extra 2:00pm weekday Mincha** — appears across many 5785/5786 winter weeks (wk15 "2:00pm & 8:00pm"; wk23-25 "2:00pm & 7:15pm"; wk08-13 "2:00pm & 7:2x/7:3x/7:4xpm"; wk37-40 "2:00pm & 4:4xpm") with **no stated occasion**. Is this a standing daily early-Mincha minyan added in a certain season, or occasion-specific? It is not tied to any single festival. **Needs a trigger rule.**
2. **Extra 9:00/9:15am Chanukah Shacharis** — recurs both Chanukah years but the sheet never states why. Hallel/late-riser/school-holiday minyan? Confirm so the generator knows when to add it (whole of Chanukah? weekdays only?).
3. **Extra 9:15am Shacharis on a plain Friday in Aseret Yemei Teshuva (5786, 3 Oct)** — reason unrecorded.
4. **Erev Yom Kippur "Early Mincha + lekach" clock time** — 4:30pm (5785) vs 3:15pm (5786). Fixed time, proportional-hour anchor, or Rov's call each year?
5. **Erev RH duplicate Maariv (5:40 & 6:20)** — is 6:20 a later option, or a leftover?
6. **"Under the Stars" Shmini Atzeres naming** — the task brief expects it; the corpus only shows an unnamed "Children's program including Hakofos 6:30–8:00pm". Is "Under the Stars" the marketing name for that program? Confirm so it can be emitted.
7. **First-Purim-minyan 6:05am vs 6:15am** — does the earlier 6:05 apply only when Purim is a weekday (Tues) vs 6:15 when Friday? Confirm.
8. **Season cutoff for early-minyan / halacha-shiur** (Rule 12g) — what luach/clock condition ends and resumes them?
9. **Public-holiday schedules with no printed label** — the generator will need an authoritative AU (NSW) public-holiday feed; confirm the shul wants holidays auto-detected and the "public holidays" note auto-printed.

---

## Coverage gaps (special days presumably observed but absent from the corpus)

The following appear in no sheet; the shul should supply the intended lines/behaviour:

- **Tu B'Shvat (15 Shevat)** — no item at all. (Yud Shevat is present; Tu B'Shvat is not.)
- **Rosh Chodesh Kislev** — absent (explicitly requested to check; not found).
- **Yud-Tes / Chof Kislev (19–20 Kislev, Chag HaGeulah / "Rosh Hashana of Chassidus")** — absent; a major Chabad date, would expect a farbrengen. Likely just not in the sampled weeks.
- **Chof-Ches / Chof-Beis Nisan, Pesach Sheni farbrengen details** — Pesach Sheni present as a label only.
- **Gimmel Tammuz full program**, **12–13 Tammuz** in years other than 5782 — only stubs ("Details TBA").
- **Chamisha-Asar B'Av (15 Av)** — appears only as the end-date of Nine-Days restrictions, never as its own celebratory item.
- **Yud-Beis / Yud-Gimmel Tammuz** beyond the single 5782 stub.
- **Kinus Torah at Shavuos** — Kinus Torah parts appear at Pesach and Succos but **not** in the Shavuos sheet; confirm whether Shavuos should also carry Kinus Torah parts.
- **Sotah shiur / other Yom-Tov night learning cycles** — only the post-Pesach Sotah shiur is attested (1 instance).
- **Selichos "goral" and first-Selichos farbrengen** — 1 instance (5785); confirm it recurs every year.
- **An explicit AU public-holiday table** — needed to drive §12h; not derivable from the zmanim engine.
- **Distinct engine zmanim** for **sha'a asiris** and **sof achilas/biur chometz** — the engine returned no offset candidate for sha'a asiris (Rules 4e/6a) and re-used `sof_tfila` for the chometz-eating deadline; confirm these are computed directly.
