# Notificaciones por correo

Cada noche se envía a cada usuario **un solo correo** con lo que le aplica ese día. Si no tiene nada que avisar, no recibe correo.

No corre dentro de la app Streamlit: es un script que se ejecuta una vez, envía y termina. Lo programa GitHub Actions (gratis), así que no consume recursos de la app.

## Qué avisa

| Aviso | Cuándo sale | A quién |
|---|---|---|
| **Correspondencia** vencida y por vencer (tabla con radicado, asunto, fecha y días hábiles) | Cada noche de día hábil mientras tenga radicados vencidos o que venzan en los próximos 5 días | Al responsable del radicado |
| **Apertura de formatos de contrato** | Una vez por mes, la noche del día configurado en el parámetro "Día de inicio del período de certificación" (si esa noche no corre, sale en una de las dos siguientes) | A los usuarios con contrato vigente |
| **Avance de firmas** (qué firmas tiene el formato y cuáles faltan) | Solo cuando el formato recibió una firma nueva desde el último aviso | Al contratista dueño del formato |

El aviso de firmas cubre el Formato de control Corr-GD-SECOP, el Acta de compromiso, el Balance General CPS y el Acta de recibo y entrega CPS. En los dos últimos indica cuándo ya se puede descargar el PDF (firmas de Financiera y Jurídico).

Solo reciben correo los usuarios **activos** con un correo válido en su perfil.

## Una vez al día o al momento del cambio

En **Administración → Parámetros** está el parámetro **"Notificaciones por correo — momento del envío"**:

| Opción | Qué hace |
|---|---|
| **Una vez al día** (por defecto) | Todo sale en el resumen de la noche. |
| **Al momento del cambio** | El aviso de avance de firmas se envía de inmediato cuando el firmante firma. |

El parámetro solo cambia el aviso de **firmas**, que es el único que nace de un cambio. La correspondencia vencida y la apertura de formatos dependen de la fecha, así que siempre van en el resumen de la noche.

En modo "al momento" el correo lo envía la propia aplicación al registrar la firma (en segundo plano, sin demorar la pantalla del firmante). Para eso la app también necesita `CORREO_REMITENTE` y `CORREO_PASSWORD_APP` en su configuración (los *Secrets* de Streamlit Cloud). Si ese envío falla o la app no tiene esos datos, el aviso sale igual en el resumen de la noche.

## Diseño del correo

- Logo de INVIAS (va embebido dentro del correo, no se descarga de internet), naranja corporativo y tonos café y crema.
- Saludo con el nombre del usuario y la fecha.
- **Sin ningún enlace.** Además, si el asunto de un radicado trae una URL o un correo, se reemplaza por "[enlace omitido]" para que el programa de correo no lo convierta en enlace.
- Vista previa con datos de ejemplo: `docs/vista_previa/correo_notificaciones.html`.

## Puesta en marcha

### 1. Contraseña de aplicación de Gmail

Gmail no deja enviar correos desde un programa con la contraseña normal de la cuenta. Se necesita una **contraseña de aplicación**:

1. Entrar a la cuenta remitente y activar la **verificación en dos pasos**.
2. En la cuenta de Google, buscar **Contraseñas de aplicaciones**, crear una (nombre sugerido: "SRTI notificaciones") y copiar las 16 letras que entrega.

Esa contraseña de 16 letras es la que se usa abajo. Nunca se escribe en el código ni se sube al repositorio.

### 2. Secretos en GitHub

En el repositorio: **Settings → Secrets and variables → Actions → New repository secret**. Crear:

| Secreto | Valor |
|---|---|
| `MONGODB_URI` | La misma cadena de conexión que usa la app |
| `MONGODB_DB` | El nombre de la base de datos |
| `SECRET_KEY` | La misma clave secreta de la app |
| `CORREO_REMITENTE` | La dirección de la cuenta remitente |
| `CORREO_PASSWORD_APP` | La contraseña de aplicación de 16 letras |

MongoDB Atlas debe permitir conexiones desde GitHub (en **Network Access**, la misma apertura que ya necesita Streamlit Cloud).

### 3. Base de datos

```bash
python -m app.scripts.init_db
```

Crea la colección `notificaciones_correo`, donde se anota qué ya se avisó para no repetirlo.

### 4. Activar la programación

El archivo `.github/workflows/notificaciones.yml` programa el envío todos los días a las **8:00 p. m. hora de Bogotá** y la limpieza del registro los lunes a las 00:05. GitHub solo ejecuta programaciones que estén en la rama principal (`main`), así que empieza a funcionar cuando ese archivo llegue a `main`.

Para cambiar las horas, editar las líneas `cron` (están en hora UTC: Bogotá + 5 horas).

## Probar antes de activar

Con las variables `CORREO_REMITENTE` y `CORREO_PASSWORD_APP` en el `.env` local:

```bash
python -m app.scripts.enviar_notificaciones --simular
```

Solo cuenta cuántos correos saldrían; no envía ni registra nada.

```bash
python -m app.scripts.enviar_notificaciones --simular --guardar-en vista_previa
```

Además guarda el HTML de cada correo para revisarlo.

```bash
python -m app.scripts.enviar_notificaciones --prueba-a micorreo@ejemplo.com
```

Envía hasta 3 correos reales a esa dirección (no a sus dueños) y no los marca como enviados.

En GitHub también se puede lanzar a mano desde **Actions → Notificaciones por correo → Run workflow**; por defecto corre en modo simulación.

## Qué se guarda en la base de datos y cómo se limpia

El contenido de los correos **no se guarda** en la base de datos (queda en "Enviados" de la cuenta remitente). Solo se guarda, en la colección `notificaciones_correo`, una marca por aviso enviado (usuario, tipo, a qué corresponde y fecha), que sirve para no repetirlo.

Cada **lunes a las 00:05** (hora de Bogotá) se borran esas marcas. Se conservan únicamente las de los últimos 3 días, que son las que todavía evitan repetir un aviso; esas se borran en la limpieza de la semana siguiente. Borrarlas todas haría que un contratista recibiera dos veces el aviso de una firma de ese fin de semana.

Para hacer la limpieza a mano:

```bash
python -m app.scripts.enviar_notificaciones --limpiar
```

## Comportamiento ante fallos

- Si el script corre dos veces el mismo día, no repite avisos.
- Si el correo de un usuario falla, los demás se envían igual y el suyo se reintenta la noche siguiente.
- Si una noche no corre, la siguiente recoge las firmas de los últimos 3 días y el aviso de formatos si aún está dentro de sus 3 días.
- El registro de ejecución solo muestra totales: no imprime nombres ni direcciones.

## Límites a tener en cuenta

- Gmail gratuito permite alrededor de 500 destinatarios por día.
- GitHub puede retrasar la ejecución programada algunos minutos, y **desactiva las programaciones de un repositorio sin actividad durante 60 días** (se reactivan desde la pestaña Actions).

## Código

- `app/scripts/enviar_notificaciones.py` — punto de entrada.
- `app/services/notificacion_service.py` — qué se avisa a quién.
- `app/core/plantillas_correo.py` — diseño del correo.
- `app/services/correo_service.py` — envío por SMTP.
- `app/repositories/notificacion_repo.py` — registro de avisos enviados.
- `tests/test_notificaciones_correo.py` — pruebas.
