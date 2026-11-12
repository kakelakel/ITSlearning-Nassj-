# itslearning för Home Assistant

Inofficiell Home Assistant-integration som hämtar läxor, deadlines och schema från itslearning, för skolor där eleven loggar in via **Skolfederation**. Byggd och testad för Nässjö kommun (`nassjo.itslearning.com` → Höglandsportalen), men flödet är generiskt.

Med i repot:
- **Integrationen** (`custom_components/itslearning`) med sensorer, två kalendrar och en synk-åtgärd.
- **En färdig skolpanel** för Lovelace (`lovelace/itslearning-dashboard.yaml`).
- **Ett paket** (`packages/itslearning.yaml`) med synk till Google Kalender och en läxpåminnelse kl. 18.

> Inte kopplad till eller godkänd av itslearning AS eller Nässjö kommun. Den kan sluta fungera om itslearning eller kommunen ändrar sin inloggning.

## Entiteter

itslearning har inget lektionsschema, det ligger oftast i ett annat system som Skola24. Integrationen hämtar det som lärarna lägger in i itslearning:

| Entitet | Beskrivning |
|---|---|
| `sensor.itslearning_today` / `_tomorrow` | Allt för dagen: händelser, planering och deadlines (attributen `events`, `plans`, `tasks`). |
| `sensor.itslearning_upcoming_events` | Läxförhör, prov och andra händelser kommande 14 dagar. |
| `sensor.itslearning_plans_this_week` / `_next_week` | Lektionsplanering per kurs ("5.1 Liv i samspel – s. 126–133"). |
| `sensor.itslearning_upcoming_tasks` | Uppgifter med deadline framåt. |
| `sensor.itslearning_due_tomorrow` | Uppgifter med deadline före midnatt i morgon. |
| `sensor.itslearning_overdue_tasks` | Ej klara uppgifter där deadline har passerat. |
| `sensor.itslearning_tasks_without_deadline` | Ej klara uppgifter utan deadline. |
| `sensor.itslearning_next_deadline` | Tidpunkt för nästa deadline. |
| `sensor.itslearning_news` | Nyheter från lärarna (antal senaste veckan, lista i `news`). |
| `sensor.itslearning_unread_notifications` | Olästa notiser. |
| `calendar.itslearning_events` | Händelser från itslearnings kalender. |
| `calendar.itslearning_plans` | Planering som heldagshändelser. |
| `calendar.itslearning_deadlines` | Deadlines (30 min, slutar vid deadline). |

Kurskoder översätts till ämnen, till exempel `BR7E/SV` → Svenska och `M2DEU/BR7` → Tyska. Data hämtas var 30:e minut. Med ett andra barn får entiteterna ändelsen `_2`.

## 1. Testa inloggningen

```bash
pip install aiohttp
python3 test_login.py            # Windows: py test_login.py
python3 test_login.py --debug    # visar varje steg
```

Skriptet visar uppgifter, händelser, planering och nyheter och testar att förnya token. `--explore` visar rådata från alla delar av API:et.

## 2. Installera integrationen

**HACS:** ⋮ → *Custom repositories* → `https://github.com/kakelakel/ITSlearning-Nassj-`, typ *Integration* → installera *itslearning* → starta om Home Assistant.

Sedan: *Inställningar → Enheter och tjänster → Lägg till integration → itslearning*.

## 3. Skolpanelen

*Inställningar → Instrumentpaneler → Lägg till instrumentpanel → Ny från början*. Öppna den, välj ⋮ → *Redigera* → ⋮ → *Raw-konfigurationsredigerare* och klistra in innehållet i `lovelace/itslearning-dashboard.yaml`.

Panelen visar:
- **Idag / I morgon:** läxförhör, prov, deadlines och dagens planering med beskrivning.
- **Planering denna vecka:** per veckodag. Nästa vecka ligger under en utfällbar rubrik.
- **Läxor & prov:** färg efter hur bråttom det är. Försenade visas i rött och uppgifter utan deadline ligger under en utfällbar rubrik.
- **Nyheter från lärarna.**
- **Kalender:** veckolista med händelser, planering och deadlines.
- **Google:** synka nu, och av/på för automatisk synk.

Panelen använder bara inbyggda kort.

## Kort till din egen panel

Integrationen har ett eget kort, `custom:itslearning-card`, som laddas automatiskt. Du behöver inte lägga till någon resurs eller installera något via HACS. Välj **Redigera panel → Lägg till kort**, sök efter **itslearning** och ställ in allt i den visuella editorn. Fler färdiga exempel finns i [`lovelace/card-examples.yaml`](lovelace/card-examples.yaml).

![Stilar 1](docs/card-presets-1.png)
![Stilar 2](docs/card-presets-2.png)

```yaml
type: custom:itslearning-card
view: homework
preset: glass
```

### Vyer (`view`)

| Värde | Visar |
|---|---|
| `day` | Idag och i morgon (standard). |
| `today` / `tomorrow` | En dag: händelser, deadlines och planering. |
| `homework` | Läxförhör, prov och deadlines, grupperat per dag. Visar även försenade och uppgifter utan deadline. |
| `week` / `next_week` | Lektionsplanering per dag. |
| `news` | Nyheter från lärarna. |
| `next` | En rad med nästa läxa eller prov. |
| `chips` | Snabbsiffror: i morgon, prov, försenade, nyheter, olästa. Tryck för detaljer. |
| `overview` | Allt i ett kort. |

### Stilar (`preset`)

`default` (följer ditt tema), `glass`, `neon`, `minimal`, `solid`, `notebook`, `sunset`, `ocean`, `midnight`. En stil är en startpunkt. Allt du ställer in själv skriver över den.

### Alla inställningar

Färger anges som `[r, g, b]`, `"#rrggbb"` eller en CSS-färg som `"var(--accent-color)"`.

| Inställning | Standard | Beskrivning |
|---|---|---|
| `title`, `icon` | per vy | Egen rubrik och ikon. |
| `show_header`, `show_count` | `true` | Rubrikrad och antal. |
| `show_events`, `show_tasks`, `show_plans` | `true` | Vad som tas med. |
| `show_overdue`, `show_no_deadline` | `true` | Extra delar i `homework`. |
| `show_description`, `description_lines` | `true`, `2` | Beskrivningar och hur många rader de får ta. |
| `show_subject_color`, `subject_bar_width` | `true`, `3` | Ämnesfärgad linje från itslearning. |
| `show_icons`, `icon_style` | `true`, `mdi` | `mdi` eller `emoji`. |
| `group_by_day` | `true` | Dagkolumn till vänster. |
| `link_items` | `true` | Rader öppnar itslearning. |
| `max_items`, `days_ahead` | `8`, `14` | Hur mycket som visas. |
| `empty_text` | – | Egen text när listan är tom. |
| `entity_suffix` | – | `_2` för ett andra barn. |
| `background_color`, `background_opacity` | tema, `100` | Bakgrund och täckning i procent. 0 betyder genomskinligt. |
| `blur` | `0` | Oskärpa bakom kortet (glas), i px. |
| `gradient`, `gradient_color`, `gradient_angle` | `false` | Gradient från bakgrundsfärgen. |
| `ruled` | `false` | Linjerat papper med marginallinje. |
| `text_color`, `secondary_text_color`, `accent_color` | tema | Textfärger och accent. |
| `font_scale` | `100` | Textstorlek i procent. |
| `border_width`, `border_style`, `border_color`, `border_opacity`, `border_radius` | tema | Kantlinje: `solid`, `dashed`, `dotted` eller `double`. |
| `shadow` | tema | Skuggans storlek, 0–80. |
| `glow`, `glow_color`, `glow_size`, `glow_intensity` | `false` | Glöd runt kortet. |
| `glow_animation` | `none` | `pulse`, `breathe` eller `rainbow`. Stängs av om enheten har reducerad rörelse påslagen. |
| `item_style` | `plain` | `plain`, `tinted`, `outlined` eller `bar` (tonad med ämnesfärg). |
| `item_background_opacity`, `item_radius`, `item_spacing`, `padding` | | Radernas utseende och avstånd. |
| `today_color`, `tomorrow_color`, `soon_color`, `later_color`, `overdue_color` | röd, orange, gul | Färg på dagkolumnen efter hur bråttom det är. |
| `chips` | alla | Vilka chips som visas, t.ex. `[tomorrow, overdue_tasks]`. |

## 4. Google Kalender

1. Lägg till Home Assistants integration **Google Calendar** och ge den läs- och skrivrättighet. Skapa gärna en egen Google-kalender, till exempel "Freja skola", och välj den.
2. Kopiera `packages/itslearning.yaml` till `config/packages/`. Lägg också till detta i `configuration.yaml` om det inte redan finns:
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```
3. Byt `calendar.DIN_GOOGLE_KALENDER` och `notify.mobile_app_DIN_TELEFON` i filen och starta om.

Synken körs varje timme och lägger bara till **nya** händelser. Varje händelse får en markering `[itsl:…]` i beskrivningen, så den läggs aldrig in två gånger. Som standard synkas deadlines och händelser (läxförhör, prov). Ta bort `#` framför `- plans` om även planeringen ska in.

Påminnelsen kl. 18 skickas bara när något är inlagt för i morgon.

Begränsning: Home Assistant kan inte ta bort eller flytta händelser i en annan kalender. Om en lärare flyttar en deadline läggs den nya tiden in, men den gamla ligger kvar tills du tar bort den.

Åtgärden kan också köras för hand under *Utvecklarverktyg → Åtgärder → itslearning: Synka till kalender*.

## Hur inloggningen fungerar

Integrationen gör samma sak som itslearning-appen:

1. Öppnar itslearnings OAuth-inloggning och väljer **Logga in med Skolfederation**.
2. Väljer **Användarnamn och lösenord** i Höglandsportalen och skickar uppgifterna.
3. Följer SAML-svaret tillbaka till itslearning och läser app-koden som sidan lämnar över med JavaScript.
4. Byter koden mot en åtkomsttoken och en förnyelsetoken.

Förnyelsetoken sparas, så hela inloggningen görs bara när den slutar gälla. Användarnamn och lösenord sparas lokalt i Home Assistant. BankID och SMS stöds inte.

## Felsökning

```yaml
logger:
  logs:
    custom_components.itslearning: debug
```

- **Inloggningen misslyckas:** kör `test_login.py --debug` och se var det stannar.
- **Något saknas:** kör `test_login.py --explore` och se vad itslearning faktiskt skickar.
- **Statusvärden:** uppgifter räknas som klara när status är till exempel `Completed` eller `Submitted`.

## Licens

MIT
