# Activity 3 - SOLID y arquitectura hexagonal con FastAPI y PostgreSQL

API de un sistema de almacenamiento de ficheros. Parte de la segunda entrega y sustituye el
estado en memoria por PostgreSQL, reorganizando cada modulo en arquitectura hexagonal.

## Estructura

Cada uno de los dos modulos, `authentication` y `files`, tiene las mismas cuatro capas:

```
app/authentication/
  models.py                definiciones de Tortoise para la base de datos
  api/                     routers y esquemas de entrada y salida
  domain/                  entidades, puertos y logica de negocio
  persistence/             implementaciones de los puertos contra Postgres
  dependency_injection/    singletons que enlazan la API con el dominio
```

La regla de dependencia va siempre hacia dentro: la API conoce al dominio, la persistencia
implementa los puertos que el dominio declara, y el dominio no importa nada de las otras capas.
En `app/authentication/domain/services.py` no aparece FastAPI ni Tortoise por ningun lado.

### Como se aplica cada principio

- **Responsabilidad unica.** El router traduce HTTP, el servicio decide, el repositorio guarda.
  Un cambio de codigo de respuesta se queda en `api`, un cambio de consulta en `persistence`.
- **Abierto/cerrado.** Anadir otro formato de fusion o cambiar pypdf por otra libreria es escribir
  un adaptador nuevo de `PdfMerger`, sin tocar `FileService`.
- **Sustitucion de Liskov.** Las pruebas de `tests/test_domain.py` sustituyen los repositorios de
  Postgres por dobles en memoria y el servicio funciona igual, sin condicionales por tipo.
- **Segregacion de interfaces.** Los puertos son pequenos y separados: `UserRepository`,
  `SessionRepository`, `PasswordHasher`, `TokenGenerator`, `FileRepository`, `PdfMerger` y
  `UserResolver`. Nadie depende de metodos que no usa.
- **Inversion de dependencias.** Los servicios reciben los puertos por constructor y quien decide
  las implementaciones concretas es `dependency_injection`, no ellos.

### Relacion entre los dos modulos

`files` necesita saber a que usuario pertenece un token, pero no depende de
`AuthenticationService`: declara el puerto `UserResolver` y en `persistence/identity.py` vive el
adaptador que resuelve el token contra el modulo de autenticacion. Cambiar la autenticacion por un
proveedor externo seria reescribir ese adaptador y nada mas.

## Base de datos

PostgreSQL con Tortoise como ORM. Tres tablas:

| Tabla | Contenido |
| --- | --- |
| `users` | clave primaria interna, identificador externo unico, correo, nombre y hash |
| `sessions` | token como clave primaria y referencia al usuario |
| `files` | metadatos, contenido binario y el identificador externo del propietario |

`files.owner_external_id` es una clave ajena real contra `users.external_id`, con borrado en
cascada: al eliminar un usuario desaparecen sus ficheros y sus sesiones.

### Migraciones

Se gestionan con aerich y estan versionadas en `migrations/`.

```bash
docker compose --profile tools run --rm make_migrations   # aerich migrate
docker compose --profile tools run --rm migrate           # aerich upgrade
```

Al arrancar, la aplicacion crea las tablas que falten a partir de los modelos. Se puede desactivar
con `GENERATE_SCHEMAS=false` en el fichero de entorno para dejar el esquema exclusivamente en manos
de las migraciones, que es lo razonable en un despliegue real.

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
| GET | `/files/{id}` | Informacion del fichero y su contenido en base64 |
| POST | `/files/{id}` | Sube el contenido del fichero (multipart) |
| DELETE | `/files/{id}` | Borra el fichero |
| POST | `/files/merge` | Fusiona varios PDFs y devuelve el id del resultado |

La creacion esta partida en dos llamadas a proposito: `POST /files` registra los metadatos y
`POST /files/{id}` sube el contenido binario.

## Decisiones de diseno

- **El identificador externo no es la clave primaria.** Se genera aleatorio y unico, y es el unico
  que sale de la aplicacion. Asi no se filtra cuantos usuarios hay ni se depende de la secuencia
  interna de Postgres.
- **Los errores de negocio no saben de HTTP.** El dominio lanza excepciones propias
  (`EmailAlreadyRegistered`, `FileNotFound`...) y `app/main.py` las traduce a codigos. Reusar el
  dominio desde una cola de mensajes o una CLI no arrastraria FastAPI.
- **404 en lugar de 403 para ficheros ajenos.** Con un 403 se estaria confirmando que ese id existe.
- **Correo como identificador de usuario.** Ya lo valida pydantic y evita resolver colisiones de
  nombres de usuario.
- **Contenido binario en la propia base de datos.** Con ficheros pequenos evita tener que montar
  almacenamiento compartido entre replicas. Si creciera, el cambio quedaria contenido en
  `TortoiseFileRepository`.
- **Contrasenas con PBKDF2-HMAC-SHA256** y 200.000 iteraciones, comparadas con
  `hmac.compare_digest` para no filtrar informacion por el tiempo de respuesta.
- **Singletons con `lru_cache`.** Los servicios no guardan estado por peticion, asi que se construye
  uno solo por proceso en lugar de rehacer el grafo de dependencias en cada llamada.

## Codigos de respuesta

| Codigo | Cuando |
| --- | --- |
| 200 | Operacion correcta |
| 400 | Fusion imposible: falta contenido o el PDF no es valido |
| 401 | Credenciales incorrectas o token de sesion no valido |
| 404 | El fichero no existe o no pertenece al usuario |
| 409 | El correo ya esta registrado |
| 422 | Cuerpo, cabecera `Auth` o lista de ficheros a fusionar mal formados |

## Puesta en marcha

```bash
docker compose up --build api
```

Levanta Postgres y la API. La documentacion swagger queda en `http://localhost:8000/docs`.

Entorno de desarrollo con recarga automatica:

```bash
docker compose --profile dev up --build api-dev
```

## Pruebas

```bash
docker compose --profile dev run --rm api-dev python -m pytest -q
```

- `tests/test_domain.py`: dominio aislado con dobles en memoria, sin base de datos.
- `tests/test_api.py`: la API completa contra Postgres, incluido el aislamiento entre usuarios y la
  fusion de tres PDFs comprobando que el resultado suma las paginas de todos.

## Formateo del codigo

```bash
docker compose --profile tools run --rm format
```

## Servicios de docker-compose

| Servicio | Para que |
| --- | --- |
| `db` | PostgreSQL 16 con volumen persistente |
| `api` | Imagen de produccion |
| `api-dev` | Desarrollo con recarga automatica |
| `make_migrations` | `aerich migrate` |
| `migrate` | `aerich upgrade` |
| `format` | black y ruff |
