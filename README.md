# Activity 4 - Almacenamiento de objetos y cache con Redis y S3

API de un sistema de almacenamiento de ficheros. Parte de la tercera entrega y mueve la
persistencia al sistema que le corresponde a cada dato: los tokens de sesion a Redis y el
contenido de los ficheros a S3, dejando en PostgreSQL solo lo relacional.

Imagen publicada: **https://hub.docker.com/r/seifreed/activity_4**

## Que guarda cada sistema

| Dato | Donde | Por que |
| --- | --- | --- |
| Usuarios y metadatos de ficheros | PostgreSQL | Son datos relacionales con integridad referencial |
| Tokens de sesion | Redis | Caducan solos con un TTL y se comparten entre workers |
| Contenido de los ficheros | S3 (MinIO en local) | Escala aparte de la API y permite descargas directas |

Ninguno de los tres aparece en el dominio. Cada uno entra por un puerto y su implementacion se
elige en `dependency_injection`, asi que se pueden cambiar sin tocar la logica de negocio.

## Estructura

Cada uno de los dos modulos, `authentication` y `files`, mantiene las mismas cuatro capas:

```
app/authentication/
  models.py                definiciones de Tortoise para la base de datos
  api/                     routers y esquemas de entrada y salida
  domain/                  entidades, puertos y logica de negocio
  persistence/             implementaciones de los puertos
  dependency_injection/    singletons que enlazan la API con el dominio
```

## Redis como cache de sesiones

`RedisSessionRepository` implementa el mismo puerto `SessionRepository` que ya usaba Postgres.
Guarda junto al token una instantanea del usuario en JSON, de modo que validar una peticion no
necesita ninguna consulta a la base de datos.

Dos cosas que se ganan y que con una tabla no se tenian:

- **Caducidad automatica.** La clave se escribe con un TTL (`SESSION_TTL_SECONDS`), asi que las
  sesiones viejas desaparecen solas y no hace falta ninguna tarea de limpieza.
- **Estado compartido.** Varios workers o varias replicas de la API ven las mismas sesiones sin
  pasar por Postgres en cada peticion.

Las dos implementaciones conviven y se elige con `SESSION_BACKEND=redis|postgres` en el fichero de
entorno. Es el mismo contrato, asi que `AuthenticationService` no nota el cambio.

## S3 como almacenamiento de objetos

El contenido binario ya no esta en la base de datos: la tabla `files` guarda `object_key`, que
apunta al objeto en el bucket, y su tamano. `S3ObjectStorage` implementa el puerto `ObjectStorage`
con boto3, que sirve igual para MinIO en local y para AWS en produccion cambiando el endpoint.

Las claves se construyen como `{identificador externo}/{id del fichero}/{uuid}`, de forma que los
objetos de cada usuario quedan bajo su propio prefijo.

`GET /files/{id}` devuelve ademas un `download_url`: un enlace prefirmado y temporal contra S3
(`S3_URL_EXPIRATION_SECONDS`, 15 minutos por defecto). Es la forma de repartir ficheros sin que el
contenido pase por la API, que es justo lo que hace interesante a S3 en un servicio con trafico.
Los enlaces se firman contra `S3_PUBLIC_ENDPOINT_URL`, que es la direccion que ve el cliente:
dentro de la red de docker el servicio se llama `storage`, pero desde fuera es `localhost`.

El servicio se encarga de que la fila y el objeto no se separen: al reemplazar contenido borra el
objeto anterior y al borrar un fichero borra tambien el suyo.

## Endpoints

El token de sesion siempre viaja en la cabecera **`Auth`**.

| Metodo | Ruta | Descripcion |
| --- | --- | --- |
| POST | `/authentication/register` | Alta de usuario, devuelve su identificador externo |
| POST | `/authentication/login` | Devuelve el token de sesion |
| POST | `/authentication/logout` | Invalida el token recibido |
| GET | `/authentication/introspect` | Valida el token y devuelve el usuario |
| GET | `/files` | Lista los ficheros del usuario |
| POST | `/files` | Crea el fichero con su informacion y devuelve el id |
| GET | `/files/{id}` | Informacion, contenido en base64 y enlace de descarga |
| POST | `/files/{id}` | Sube el contenido del fichero (multipart) |
| DELETE | `/files/{id}` | Borra el fichero y su objeto |
| POST | `/files/merge` | Fusiona varios PDFs y devuelve el id del resultado |

## Puesta en marcha

```bash
docker compose up --build api
```

Levanta PostgreSQL, Redis, MinIO y la API. Swagger en `http://localhost:8000/docs` y la consola de
MinIO en `http://localhost:9001` (usuario y contrasena en el fichero de entorno).

El bucket se crea al arrancar si no existe, igual que el esquema de la base de datos.

Desarrollo con recarga automatica:

```bash
docker compose --profile dev up --build api-dev
```

## Migraciones

```bash
docker compose --profile tools run --rm make_migrations   # aerich migrate
docker compose --profile tools run --rm migrate           # aerich upgrade
```

## Pruebas

```bash
docker compose --profile dev run --rm api-dev python -m pytest -q
```

- `tests/test_domain.py`: dominio aislado con dobles en memoria. Al estar el almacenamiento detras
  de un puerto, se comprueba sin Postgres, sin Redis y sin S3.
- `tests/test_api.py`: la API completa contra los tres servicios reales, incluida la caducidad de
  la sesion en Redis y la descarga efectiva por el enlace prefirmado.

## Formateo del codigo

```bash
docker compose --profile tools run --rm format
```

## Integracion continua

- `.github/workflows/format.yml`: en cada pull request comprueba el formato con black y ruff.
- `.github/workflows/publish.yml`: construye y publica la imagen en Docker Hub. Necesita los
  secretos `DOCKERHUB_USERNAME` y `DOCKERHUB_TOKEN` en el repositorio.

## Servicios de docker-compose

| Servicio | Para que |
| --- | --- |
| `db` | PostgreSQL 16 con volumen persistente |
| `cache` | Redis 7 para los tokens de sesion |
| `storage` | MinIO como S3 local, con su volumen |
| `api` | Imagen de produccion |
| `api-dev` | Desarrollo con recarga automatica |
| `make_migrations` | `aerich migrate` |
| `migrate` | `aerich upgrade` |
| `format` | black y ruff |

## Decisiones de diseno

- **Cada dato en el sistema que le va.** Las sesiones son efimeras y de acceso constante, asi que
  van a una cache con caducidad. El contenido son objetos grandes e inmutables, asi que va a un
  almacen de objetos. Lo relacional se queda en Postgres.
- **Se mantiene el contenido en base64 en `GET /files/{id}`.** El enunciado pide devolver el
  contenido si esta presente, pero se acompana del enlace prefirmado, que es lo que se usaria de
  verdad para no cargar el servidor con las descargas.
- **El identificador externo no es la clave primaria** y es el unico que sale de la aplicacion.
- **Los errores de negocio no saben de HTTP.** El dominio lanza excepciones propias y `app/main.py`
  las traduce a codigos de respuesta.
- **404 en lugar de 403 para ficheros ajenos.** Con un 403 se estaria confirmando que ese id existe.
- **boto3 en el executor.** La libreria es sincrona, asi que cada llamada se lanza fuera del bucle
  de eventos para que una transferencia no bloquee al resto de peticiones.

## Codigos de respuesta

| Codigo | Cuando |
| --- | --- |
| 200 | Operacion correcta |
| 400 | Fusion imposible: falta contenido o el PDF no es valido |
| 401 | Credenciales incorrectas o token de sesion no valido o caducado |
| 404 | El fichero no existe o no pertenece al usuario |
| 409 | El correo ya esta registrado |
| 422 | Cuerpo, cabecera `Auth` o lista de ficheros a fusionar mal formados |

<!-- prueba del check de formato -->
