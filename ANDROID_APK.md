# APK Android (testeo y build)

> **Seguridad:** si alguna vez pegaste un token de Expo en un chat o en un archivo del repo, **revócalo ya** en [expo.dev → Access tokens](https://expo.dev) y crea otro; el nuevo va **solo** en GitHub → *Secrets* → `EXPO_TOKEN`. Ver [SECURITY.md](./SECURITY.md).

## Para ti: generar el `.apk`

1. Instala dependencias: `npm install`
2. Inicia sesión en Expo: `npx eas-cli login`
3. Si es la primera vez en este repo, vincula el proyecto (crea `expo.extra.eas.projectId` en `app.json`):
   ```bash
   npx eas-cli init
   ```
4. Compila el APK de prueba (perfil `preview` en [`eas.json`](eas.json)):
   ```bash
   npx eas-cli build -p android --profile preview
   ```
5. Cuando termine el build, descarga el `.apk` desde el enlace que muestra la CLI o desde [expo.dev](https://expo.dev).

**Builds siguientes:** sube `expo.android.versionCode` en [`app.json`](app.json) (entero mayor que el anterior) antes de cada APK que quieras instalar “encima” de otro en el mismo teléfono.

**Publicar en Google Play más adelante:** usa `npx eas-cli build -p android --profile production` (genera AAB, no APK).

### Desde GitHub (artefacto `.apk`)

El workflow [`.github/workflows/eas-android-apk.yml`](.github/workflows/eas-android-apk.yml) compila en **EAS** (nube Expo), espera a que termine, descarga el APK y lo sube como **artefacto** del run (pestaña *Actions* → workflow *EAS Android APK* → run → *Artifacts*).

1. Crea un token en Expo (cuenta → *Access tokens* en [expo.dev](https://expo.dev)) y guárdalo como secreto del repo **`EXPO_TOKEN`** (GitHub → *Settings* → *Secrets and variables* → *Actions*).
2. Asegúrate de tener **`expo.extra.eas.projectId`** en `app.json` (tras `eas init` y al menos un build bien configurado).
3. En GitHub: *Actions* → **EAS Android APK** → **Run workflow**.

El workflow también crea una **pre-release** en GitHub (*Releases*) con el `.apk` adjunto (etiqueta `android-preview-r…`), además del artefacto del run.

Los artefactos y releases de preview **no sustituyen** a Play Store para usuarios finales; sirven para testeo interno. En repos **públicos**, el APK en Releases es descargable por cualquiera.

---

## Para quien prueba la app (cocina / amigo)

1. **Instalar el APK** desde Drive, Telegram, etc. Android puede pedir permitir **instalar apps de fuentes desconocidas** para esa app concreta (Chrome, Files, etc.).
2. **Notificaciones:** en el primer arranque acepta el permiso de notificaciones. Si las rechazaste, actívalas en Ajustes → Apps → Kitchen Clock → Notificaciones.
3. **Alarmas exactas (recomendado):** en Ajustes → Apps → Kitchen Clock (o “Acceso especial”), busca **Alarmas y recordatorios** / **Alarms & reminders** y actívalo. Así el aviso del timer suele llegar a hora.
4. **Si “no suena”:** sube el volumen de **notificación** (no solo el de multimedia) y revisa que el canal de timers no esté silenciado en los ajustes de notificaciones de la app.
5. **Modo cocina por voz / sensor:** en la versión Android nativa esos modos suelen **no estar disponibles** (están pensados para la versión web). Lo importante a probar son **timers, sonido en pantalla y notificación al terminar**.

Si Play Protect avisa al instalar, es normal en apps que no están en Play Store todavía.
