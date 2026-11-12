# itslearning för Home Assistant

Inofficiell Home Assistant-integration som hämtar uppgifter och deadlines från itslearning, för skolor där eleven loggar in via **Skolfederation**. Byggd och testad för Nässjö kommun (`nassjo.itslearning.com` → Höglandsportalen), men flödet är generiskt och bör fungera i fler kommuner med inloggning via användarnamn och lösenord.

> Inte kopplad till eller godkänd av itslearning AS eller Nässjö kommun. Den kan sluta fungera om itslearning eller kommunen ändrar sin inloggning.

## Vad du får

| Entitet | Beskrivning |
|---|---|
| `sensor.…_kommande_uppgifter` | Antal ej klara uppgifter med deadline framåt. Listan finns i attributet `tasks`. |
| `sensor.…_uppgifter_till_i_morgon` | Uppgifter med deadline före midnatt i morgon. |
| `sensor.…_forsenade_uppgifter` | Ej klara uppgifter där deadline passerat. |
| `sensor.…_nasta_deadline` | Tidpunkt för nästa deadline (titel och kurs som attribut). |
| `sensor.…_olasta_notiser` | Antal olästa notiser i itslearning. |
| `calendar.…_deadlines` | Varje deadline som en händelse (30 min, slutar vid deadline). |

Data hämtas var 30:e minut.

## Hur inloggningen fungerar

Integrationen gör samma sak som itslearning-appen:

1. Öppnar itslearnings OAuth-inloggning och väljer **Logga in med Skolfederation**.
2. Väljer **Användarnamn och lösenord** i Höglandsportalen och skickar uppgifterna.
3. Följer SAML-svaret tillbaka till itslearning och får en kod som byts mot en åtkomsttoken och en förnyelsetoken.

Förnyelsetoken sparas, så den fullständiga inloggningen görs bara när token slutar gälla. Användarnamn och lösenord sparas i Home Assistant (lokalt, i `.storage`). Ingenting skickas någon annanstans än till itslearning och kommunens inloggningstjänst.

BankID och SMS stöds inte, bara användarnamn och lösenord.

## 1. Testa först

På valfri dator med Python 3.10+:

```bash
pip install aiohttp
python3 test_login.py            # lägg till --debug för att se varje steg
```

Skriptet loggar in, listar uppgifterna och testar att förnya token.

## 2. Installera

**HACS:** HACS → ⋮ → *Custom repositories* → lägg till `https://github.com/kakelakel/ITSlearning-Nassj-` som typ *Integration* → installera *itslearning* → starta om Home Assistant.

**Manuellt:** kopiera `custom_components/itslearning` till `config/custom_components/` och starta om.

Sedan: *Inställningar → Enheter och tjänster → Lägg till integration → itslearning*. Adressen är förifylld med `https://nassjo.itslearning.com`.

## Exempel: notis kl. 18 om något ska lämnas in i morgon

```yaml
automation:
  - alias: "Läxpåminnelse"
    triggers:
      - trigger: time
        at: "18:00:00"
    conditions:
      - condition: numeric_state
        entity_id: sensor.itslearning_uppgifter_till_i_morgon   # justera till ditt entitets-id
        above: 0
    actions:
      - action: notify.mobile_app_din_telefon
        data:
          title: "Läxor till i morgon"
          message: >
            {% for t in state_attr('sensor.itslearning_uppgifter_till_i_morgon', 'tasks') %}
            • {{ t.title }} ({{ t.course }}) – {{ as_timestamp(t.deadline) | timestamp_custom('%H:%M') }}
            {% endfor %}
```

## Felsökning

Slå på debug-loggning:

```yaml
logger:
  logs:
    custom_components.itslearning: debug
```

Vanliga fel:

- **Inloggningen misslyckades:** fel användarnamn/lösenord, eller att kommunen har ändrat inloggningssidan. Kör `test_login.py --debug` och se var det stannar.
- **Status för uppgifter:** itslearning anger status som text. Uppgifter räknas som klara när status är t.ex. `Completed`/`Submitted`. Om dina klara uppgifter ändå räknas som kommande, kör testskriptet och skapa ett issue med vilka statusvärden som visas.

## Licens

MIT
