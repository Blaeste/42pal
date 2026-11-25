# Plan — Le menu Testers

## Objectif

Un menu **Testers** dans le premier menu de `./42pal` : l'étudiant choisit un testeur de projet, 42pal le télécharge depuis GitHub (avec son accord, la première fois), demande le dossier du projet dans son interface, lance le testeur, lit ses résultats et les montre dans son propre style. Le premier testeur est **libfterator** (libft, sujet v19.3) ; deux autres viendront ensuite.

**Le plan est fini quand** un étudiant choisit Testers → libfterator, accepte le téléchargement, donne le chemin de sa libft, et voit la conformité, les fonctions et leurs KO dans 42pal, en anglais ou en français ; et que `./libfterator ../libft` marche toujours seul.

## Décisions (2026-11-24)

- **Tout passe par 42pal** : le lancement, la lecture des résultats (le JSON du testeur, jamais le texte du terminal), l'affichage, le chemin du projet.
- **Le testeur reste autonome** dans son repo ; pas de fork « version 42pal ». 42pal s'appuie sur un contrat : `--json FICHIER` (format versionné) et `--lang en|fr`.
- **Distribution par tag** : 42pal clone le tag fixé dans son registre (`git clone --depth 1 --branch v2.0.0`) dans `~/.42pal/testers/<nom>/`, puis vérifie que le commit est celui attendu ; sinon le dossier est supprimé. Un push sur la branche du testeur ne change rien pour 42pal ; un nouveau tag arrive avec une mise à jour de 42pal, qui propose alors de mettre le testeur à jour.
- **Le réseau** n'est utilisé que quand l'étudiant accepte le téléchargement.
- **La langue** : 42pal passe `--lang fr` quand il est en français, `--lang en` sinon. Seul, libfterator reste en français par défaut.
- **Registre** : chaque testeur est une entrée (nom, titre, dépôt, tag, commit, lanceur, systèmes) ; en ajouter un ne touche pas au reste.
- **Tester avant de publier** : `PAL42_TESTER_LIBFTERATOR=<dépôt>` remplace l'URL (un dossier local marche) ; rien n'est poussé avant les essais de l'utilisateur.

## Le contrat JSON (format 1)

```json
{"format": 1, "tester": "libfterator", "version": "2.0.0", "lang": "en", "seed": 42,
 "log": "/…/out/libfterator_….log", "error": null, "notes": [],
 "conformity": [{"key": "files.layout", "group": "Files", "label": "…", "status": "OK", "detail": ""}],
 "tests": [{"name": "strlcat/dst_not_terminated", "status": "OOB", "detail": "…", "ms": 3}]}
```

`error` vaut `{"title", "detail"}` quand le testeur n'a pas pu tourner (dossier introuvable, outil manquant, libft.a impossible à construire) ; le JSON est écrit dans tous les cas.

**Facultatif, `suites`** (Linerator, 2026-11-25) : le nom et le panneau de chaque suite, dans la langue demandée, aussi dans l'événement `plan` de `--stream` (qui peut revenir, plus petit) :

```json
"suites": [{"key": "buffer_1", "name": "BUFFER_SIZE=1", "group": "BUFFER_SIZE", "label": "1", "tests": 16}]
```

`key` est le début du nom des tests (`buffer_1/…`) ; `name` remplace la clé dans le rapport et les échecs en direct ; `group` et `label` rangent la ligne dans le panneau, `tests` dit combien de cases elle a. Avec `suites`, 42pal montre le panneau à côté du log (à partir de 100 colonnes), comme le testeur seul ; sans, rien ne change. Un `INFO` n'est compté nulle part, un `WARN` passe.

## Étapes

Chaque étape en TDD.

**Avancement (2026-11-24)** : les étapes 1 à 7 sont faites, en local. libfterator : commits 06029b2 et d0bd761, tag `v2.0.0` sur d0bd761, poussés le 2026-11-24 (le dépôt s'appelle désormais `Blaeste/Libfterator`). 42pal : le registre pointe sur ce tag et ce commit ; pas encore poussé. **À faire après les essais de l'utilisateur** : pousser 42pal.

**Suite (2026-11-24, à la demande de l'utilisateur)** : le choix du dossier simplifié et les résultats en direct. libfterator 2.1.0 (`--stream` : une ligne JSON par événement ; commit bee11bc, tag `v2.1.0`, poussés le 2026-11-24) ; 42pal épingle `v2.1.0`, cherche les dossiers qui ont un `libft.h` dans le home (largeur d'abord, 4 niveaux), les montre au fil de la recherche, propose en plein écran un chemin suivi d'une liste vivante (★, `..`, Tab) et en `--plain` un petit shell (`ls`, `cd`, `test`, numéros). Une version plus ancienne gardée tourne sans `--stream`. Les deux autres testeurs viendront ensuite, chacun avec son entrée dans le registre.

1. **libfterator** : le JSON au format 1, écrit aussi en cas d'erreur ; `--version`. *Vérif* : `checks/`.
2. **libfterator** : `--lang en` (messages Python, moteur C, tests). *Vérif* : `checks/`, run en anglais sur la référence.
3. **libfterator** : tag local `v2.0.0`, non poussé.
4. **42pal** : `pal42/testers.py` (registre, installation vérifiée, lancement, lecture du JSON). *Vérif* : tests avec un faux testeur dans un dépôt git temporaire, sans réseau.
5. **42pal** : le menu texte (Testers, téléchargement, chemin, résultats, relancer). *Vérif* : tests.
6. **42pal** : le plein écran (menu, écran du chemin avec complétion, écran des résultats avec spinner). *Vérif* : tests pilot.
7. **42pal** : `fr.json`, README. *Vérif* : `tools/locales.py check`, essai à la main.

## Risques

- **macOS** : libfterator dépend de `ld --wrap` ; 42pal ne le propose que sous Linux.
- **Outils manquants** (`cc`, `make`, `git`) : dits clairement, jamais de plantage.
- **Un testeur qui change son JSON** : `format` le signale ; 42pal refuse un format inconnu et le dit.

## Hors périmètre

- Les testeurs de tiers (licences à vérifier un par un).
- `--valgrind`, `--asan`, `--gdb` depuis 42pal (restent pour l'usage seul).

## Pushterator (2026-11-25)

Le deuxième testeur : [Pushterator](https://github.com/Blaeste/Pushterator), pour push_swap (sujet de 2026), créé à part avec l'interface de 42pal (son plan est dans son dépôt). Dans le registre : tag `v1.0.0`, son lanceur est un script shell (`python=False`), un projet se reconnaît à son Makefile qui parle de push_swap (`marker="Makefile"`, `marker_text="push_swap"`), il tourne aussi sous macOS. 42pal ne compte plus les `WARN` comme des échecs (la complexité des stratégies) et les montre, donne à chaque testeur le titre de ses tests, et résume une suite qui échoue toute de la même façon.
