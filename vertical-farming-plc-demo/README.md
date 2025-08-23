Il programma gestisce una piccola logica di controllo per una unità di coltura: controllo temperatura (heater + ventola), gestione di una pompa principale per irrigazione, dosing pH semplice (tempo fisso), protezione da livello basso e una macchina a stati che fa: irrigazione poi dosing poi wait.

Dichiariamo le variabili
VAR

Ingressi (sensori / pulsanti)
temp_raw            : INT := 2200;   (* es: centi°C -> 22.00°C *)
level_low_raw       : BOOL := FALSE; (* float switch grezzo *)
pH_measure_raw      : INT := 625;    (* pH * 100 -> 6.25 *)
start_cycle_req_raw : BOOL := FALSE; (* btn per forzare ciclo *)

Spiegazione:

temp_raw = valore grezzo della temperatura. 2200 = 22.00°C (usiamo centesimi per evitare virgole nell'hardware).

level_low_raw = float switch (TRUE = serbatoio basso).

pH_measure_raw = pH grezzo, 625 = 6.25 pH.

start_cycle_req_raw = bottone/bit per far partire la sequenza.

set_temp: la temperatura che possiamo mantenere (22°C).

hyst: isteresi per il riscaldatore (+/- 0.5°C).

fan_offset: la ventola parte solo se temp > set_temp + fan_offset (qui > 24°C).

Durate della sequenza
irrigate_duration : TIME := T#3600s;
dose_duration     : TIME := T#60s;
wait_duration     : TIME := T#60s;


irrigate_duration: quanto irrighiamo

dose_duration: quanto dura il dosing pH 

wait_duration: pausa tra cicli 

Protezioni e debounce
pump_min_off_time : TIME := T#20s;  (* min OFF per la pompa *)
debounce_time     : TIME := T#1s;   (* debounce float switch *)


pump_min_off_time: dopo che la pompa si spegne, deve rimanere OFF almeno questo tempo (anti-short-cycle).

debounce_time: il float switch deve rimanere stabile per questo tempo prima che venga considerato vero (evita falsi rimbalzi).

Variabili scalate e uscite
temp_C         : REAL;    (* temperatura in °C *)
pH_measure     : REAL;    (* pH reale *)

heater_out     : BOOL := FALSE;
fan_out        : BOOL := FALSE;
pump_out       : BOOL := FALSE;
pump_dose_out  : BOOL := FALSE;
irrigation_cmd : BOOL := FALSE;


temp_C e pH_measure sono le versioni “umane” dei raw (usate per confronti).

heater_out, fan_out, pump_out, pump_dose_out sono le uscite LOGICHE da collegare ai relè / attuatori.

Flags e timer
pump_cmd_request : BOOL := FALSE;
alarm_level_low  : BOOL := FALSE;

debounceLevelTim : TON;
pumpMinOffTim    : TON;
stateTimer       : TON;


pump_cmd_request: la macchina a stati la imposta quando vuole la pompa ON (è una richiesta).

alarm_level_low: true quando il livello è basso (dopo debounce) — blocca la pompa.

debounceLevelTim, pumpMinOffTim, stateTimer: istanze timer (TON) usate per debounce, anti-short-cycle e durata stati.

Stato macchina
STATE : INT := 0;  (* 0:IDLE,1:IRRIGATE,2:DOSE,3:WAIT *)


STATE dice in quale fase siamo: 0 ferma, 1 irrigazione, 2 dosing, 3 attesa.

Registri per SCADA/Modbus
reg_temp_raw       : INT := 0;
reg_pH_raw         : INT := 0;
reg_pump_state     : BOOL := FALSE;
reg_alarm_level    : BOOL := FALSE;


Queste copie servono per esporre i valori al SCADA via Modbus (holding registers / coils).

Fine dichiarazioni variabili
END_VAR
-------------------------------------------------------------------------------------------
Conversione raw → valori reali e copia su registri SCADA
temp_C := REAL(temp_raw) / 100.0;
pH_measure := REAL(pH_measure_raw) / 100.0;

reg_temp_raw := temp_raw;
reg_pH_raw := pH_measure_raw;


Qui trasformiamo i raw in unità leggibili (es. 2200 → 22.00°C).

Copiamo i raw nei reg_ così SCADA li legge facilmente.

Debounce sensore livello
debounceLevelTim(IN := level_low_raw, PT := debounce_time);
IF debounceLevelTim.Q THEN
  alarm_level_low := TRUE;
ELSE
  alarm_level_low := FALSE;
END_IF;

reg_alarm_level := alarm_level_low;


Avviamo il timer di debounce se level_low_raw è TRUE.

Solo se il timer finisce (cioè il livello è stabile) impostiamo alarm_level_low = TRUE.

Copiamo il flag su reg_alarm_level per SCADA.

Controllo riscaldamento con isteresi
IF temp_C < (set_temp - hyst) THEN
  heater_out := TRUE;
ELSIF temp_C > (set_temp + hyst) THEN
  heater_out := FALSE;
END_IF;


Se la temperatura scende sotto set_temp - hyst accendo il riscaldatore.

Se sale sopra set_temp + hyst lo spengo.

L’isteresi evita continue on/off vicino al setpoint.

Controllo ventola con soglia
IF temp_C > (set_temp + fan_offset) THEN
  fan_out := TRUE;
ELSE
  fan_out := FALSE;
END_IF;


La ventola parte solo se la temperatura è più alta del setpoint più fan_offset (es. > 24°C).

Così evitiamo di far partire la ventola per lievi sballi termici.

Protezione pompa (anti-short-cycle)
pumpMinOffTim(IN := NOT pump_out, PT := pump_min_off_time);


Il timer pumpMinOffTim conta quando la pompa è OFF.

Solo dopo che il timer ha contato pump_min_off_time il suo .Q diventa TRUE e la pompa può essere riaccesa.

Inibizione sicurezza e logica di accensione pompa
IF alarm_level_low THEN
  pump_cmd_request := FALSE;
  pump_out := FALSE;
ELSE
  IF pump_cmd_request AND pumpMinOffTim.Q THEN
    pump_out := TRUE;
  END_IF;
  IF NOT pump_cmd_request THEN
    pump_out := FALSE;
  END_IF;
END_IF;

reg_pump_state := pump_out;


Se il serbatoio è basso (alarm_level_low = TRUE) annullo la richiesta e spengo la pompa SUBITO.

Altrimenti, la pompa si accende solo se la macchina la richiede (pump_cmd_request) e il timer minimo OFF ha terminato (pumpMinOffTim.Q = TRUE).

Se la macchina non la richiede più, spegniamo la pompa subito.

Rilevamento del flanco (start)
start_cycle_edge := (NOT prev_start_cycle_req) AND start_cycle_req_raw;
prev_start_cycle_req := start_cycle_req_raw;


Questa riga genera start_cycle_edge = TRUE solo quando premi il pulsante (passa da 0 a 1).

È utile per far partire la sequenza una sola volta, non continuativamente.

Macchina a stati: IDLE → IRRIGATE → DOSE → WAIT
Stato 0 — IDLE
0:
  irrigation_cmd := FALSE;
  pump_cmd_request := FALSE;

  IF start_cycle_edge OR start_cycle_req_raw THEN
    STATE := 1;
    stateTimer(IN := FALSE);
  END_IF;


In IDLE non facciamo nulla.

Se arriva il flanco di start, passiamo a IRRIGATE e resettamo il timer.

Stato 1 — IRRIGATE
1:
  irrigation_cmd := TRUE;
  pump_cmd_request := TRUE;

  stateTimer(IN := TRUE, PT := irrigate_duration);
  IF stateTimer.Q THEN
    stateTimer(IN := FALSE);
    STATE := 2;
  END_IF;


Richiediamo la pompa principale.

Avviamo stateTimer per irrigate_duration (3600s). Quando finisce andiamo a DOSE.

Nota: anche se chiediamo la pompa, la pompa vera partirà solo se non c’è allarme e se pumpMinOffTim è OK.

Stato 2 — DOSE
2:
  irrigation_cmd := FALSE;
  pump_cmd_request := FALSE;

  pump_dose_out := TRUE;
  stateTimer(IN := TRUE, PT := dose_duration);
  IF stateTimer.Q THEN
    stateTimer(IN := FALSE);
    pump_dose_out := FALSE;
    STATE := 3;
  END_IF;


Disabilitiamo la pompa principale.

Accendiamo la pompa dosing (pump_dose_out := TRUE) per dose_duration.

Alla fine spegniamo dosing e andiamo in WAIT.

Nota: qui la dosing parte anche se alarm_level_low = TRUE. Se vuoi evitare questo basta aggiungere IF NOT alarm_level_low THEN pump_dose_out := TRUE;.

Stato 3 — WAIT
3:
  irrigation_cmd := FALSE;
  pump_cmd_request := FALSE;
  pump_dose_out := FALSE;

  stateTimer(IN := TRUE, PT := wait_duration);
  IF stateTimer.Q THEN
    stateTimer(IN := FALSE);
    STATE := 0;
  END_IF;


Pausa tra cicli. Tutti i comandi sono false.

Dopo wait_duration torniamo a IDLE e il ciclo è finito.

Fallback di sicurezza
ELSE
  STATE := 0;
END_CASE;

Se per qualche motivo lo stato ha un valore sbagliato, torniamo a IDLE per sicurezza.
