# itslearning för Home Assistant

Inofficiell Home Assistant-integration som hämtar läxor, deadlines och schema från itslearning, för skolor där eleven loggar in via **Skolfederation**. Byggd och testad för Nässjö kommun (`nassjo.itslearning.com` → Höglandsportalen), men flödet är generiskt.

Med i repot:
- **Integrationen** (`custom_components/itslearning`) med sensorer, två kalendrar och en synk-åtgärd.
- **En färdig skolpanel** för Lovelace (`lovelace/itslearning-dashboard.yaml`).
- **Ett paket** (`packages/itslearning.yaml`) med synk till Google Kalender och en läxpåminnelse kl. 18.

> Inte kopplad till eller godkänd av itslearning AS eller Nässjö kommun. Den kan sluta fungera om itslearning eller kommunen ändrar sin inloggning.

## Entiteter

| Entitet | Beskrivning |
|---|---|
| `sensor.itslearning_upcoming_tasks` | Ej klara uppgifter med deadline framåt (lista i attributet `tasks`). |
| `sensor.itslearning_due_tomorrow` | Uppgifter med deadline före midnatt i morgon. |
| `sensor.itslearning_overdue_tasks` | Ej klara uppgifter där deadline har passerat. |
| `sensor.itslearning_tasks_without_deadline` | Ej klara uppgifter utan deadline. |
| `sensor.itslearning_next_deadline` | Tidpunkt för nästa deadline. |
| `sensor.itslearning_schedule_today` / `_tomorrow` | Antal lektioner/händelser (lista i attributet `events`). |
| `sensor.itslearning_next_lesson` | Nästa lektion (tid, titel, sal). |
| `sensor.itslearning_next_school_day_start` | När första lektionen nästa skoldag börjar, användbart till väckning. |
| `sensor.itslearning_unread_notifications` | Olästa notiser. |
| `calendar.itslearning_schedule` | Schemat från itslearnings kalender. |
| `calendar.itslearning_deadlines` | Deadlines (30 min, slutar vid deadline). |

Data hämtas var 30:e minut. Med ett andra barn får entiteterna ändelsen `_2`.

## 1. Testa inloggningen

```bash
pip install aiohttp
python3 test_login.py            # Windows: py test_login.py
python3 test_login.py --debug    # visar varje steg
```

Skriptet visar uppgifter, kalenderhändelser och notiser och testar att förnya token.

## 2. Installera integrationen

**HACS:** ⋮ → *Custom repositories* → `https://github.com/kakelakel/ITSlearning-Nassj-`, typ *Integration* → installera *itslearning* → starta om Home Assistant.

Sedan: *Inställningar → Enheter och tjänster → Lägg till integration → itslearning*.

## 3. Skolpanelen

*Inställningar → Instrumentpaneler → Lägg till instrumentpanel → Ny från början*. Öppna den, välj ⋮ → *Redigera* → ⋮ → *Raw-konfigurationsredigerare* och klistra in innehållet i `lovelace/itslearning-dashboard.yaml`.

Panelen visar:
- **Idag:** dagens lektioner. Pågående lektion markeras och passerade gråas ut.
- **I morgon:** morgondagens lektioner.
- **Läxor:** försenade i rött och kommande med färg efter hur bråttom det är. Uppgifter utan deadline ligger under en utfällbar rubrik.
- **Vecka:** en kalenderlista med schema och deadlines.
- **Google:** en knapp för att synka till Google Kalender nu, och av/på för automatisk synk.

Panelen använder bara inbyggda kort.

## 4. Google Kalender

1. Lägg till Home Assistants integration **Google Calendar** och ge den läs- och skrivrättighet. Skapa gärna en egen Google-kalender, till exempel "Freja skola", och välj den.
2. Kopiera `packages/itslearning.yaml` till `config/packages/`. Lägg också till detta i `configuration.yaml` om det inte redan finns:
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```
3. Byt `calendar.DIN_GOOGLE_KALENDER` och `notify.mobile_app_DIN_TELEFON` i filen och starta om.

Synken körs varje timme och lägger bara till **nya** händelser. Varje händelse får en markering `[itsl:…]` i beskrivningen, så den läggs aldrig in två gånger. Som standard synkas bara läxor/deadlines. Ta bort `#` framför `- schedule` om även lektionerna ska in.

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
- **Schemat är tomt:** kör testskriptet med `--debug` och leta efter raden `Kalenderfält: […]`. Skapa ett issue med den raden. Den visar vilka fält itslearning skickar men inga personuppgifter.
- **Statusvärden:** uppgifter räknas som klara när status är till exempel `Completed` eller `Submitted`.

## Licens

MIT
