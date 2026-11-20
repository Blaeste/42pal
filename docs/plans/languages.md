# Plan — Les langues de 42pal

## Objectif

Un menu **Settings** dans le premier menu de `./42pal`, avec **Language** : anglais par défaut, puis français, allemand, russe, ukrainien, espagnol, portugais, italien et turc. La langue choisie traduit l'interface, les traces du grademe et les sujets. **Ajouter une langue, c'est ajouter des fichiers**, sans toucher au code : le menu la trouve tout seul, et un outil donne le squelette à remplir et ce qui manque.

**Le plan est fini quand** un étudiant choisit « Français » dans Settings et voit les menus, les messages, les traces et le sujet en français, que 42pal s'en souvient au lancement suivant, et que `python3 tools/locales.py check` ne signale rien pour les 9 langues.

## Décisions (2026-11-20)

- **Tout est traduit** : interface, traces, sujets. Restent en anglais : le rapport d'issue (`r`) et `check-catalog` (lus par le mainteneur), l'aide de `--help`, les noms d'exercices et de fichiers, les exemples des sujets.
- **L'anglais sert de clé** : dans le code, `t("Level {level} of {count}", level=…, count=…)`. Le catalogue `pal42/locales/fr.json` associe chaque texte anglais à sa traduction, avec `"_name": "Français"` (le nom de la langue dans sa langue, pour le menu). Pas de catalogue pour l'anglais.
- **Un texte qui manque reste en anglais** : jamais de plantage pour une traduction absente ; l'outil et les tests le signalent.
- **Sujets** : `exercises/<langage>/<nom>/locales/<code>.json` contient l'énoncé traduit (`subject`, avec les mêmes `$champs`) et les morceaux de phrase des variants (`texts`), traduits ensemble pour que les phrases restent grammaticales. L'en-tête du sujet (Assignment name, Expected files, Allowed functions) reste en anglais, comme dans les sujets de 42 ; « Examples » est traduit.
- **Fichiers du sujet** : `subjects/<nom>/subject.en.txt` toujours, plus `subject.<code>.txt` dans la langue choisie, que l'écran montre.
- **Réglage** : gardé dans `~/.42pal/settings.json` (`{"language": "fr"}`) ; `PAL42_LANG` le remplace (tests, scripts).
- **Outil** `tools/locales.py` : `new <code> "<Nom>"` crée le squelette (catalogue et sujets, valeurs vides), `check` liste par langue les textes et les sujets manquants, et les `{champs}` ou `$champs` qui ne correspondent pas.
- **Traductions** : faites par Claude ; une relecture par des étudiants dont c'est la langue est souhaitable, surtout pour les sujets.

## Étapes

Chaque étape en TDD, puis les tests utilisateur.

### Phase 1 — La mécanique

- **1.1** `pal42/i18n.py` : `t(texte, **champs)`, `set_language(code)`, `languages()` (les catalogues trouvés, plus l'anglais), repli sur l'anglais. *Vérif* : tests (traduction, champs, repli, langue inconnue).
- **1.2** Le réglage : lire et écrire `~/.42pal/settings.json`, `PAL42_LANG`, appliqué au lancement. *Vérif* : tests.
- **1.3** Settings dans le premier menu (texte et plein écran) → Language, chaque langue sous son propre nom ; le choix s'applique tout de suite et est gardé. *Vérif* : tests des deux interfaces.
- **1.4** `tools/locales.py` (`extract` lit les `t("…")` du code, `new`, `check`) et un test qui fait tourner `check` sur chaque catalogue présent. *Vérif* : tests ; un catalogue de test d'une langue factice apparaît dans le menu sans changer le code.

### Phase 2 — L'interface en français

- **2.1** Les textes de `display.py`, `shell.py`, `practice.py`, `tui.py`, `progress.py` passent par `t()`. *Vérif* : les tests existants passent sans changement (l'anglais ne bouge pas).
- **2.2** `pal42/locales/fr.json` complet. *Vérif* : `check` ne signale rien pour `fr` ; un test parcourt les menus en français.
- **2.3** La mise en page tient avec des textes plus longs (menus alignés, cartes de 64 colonnes). *Vérif* : tests avec la langue aux textes les plus longs.

### Phase 3 — Les autres langues de l'interface

- `de`, `ru`, `uk`, `es`, `pt`, `it`, `tr`. *Vérif* : `check` ne signale rien ; essai à la main de chaque menu.

### Phase 4 — Les traces

- `trace.py` passe par `t()` ; les 8 catalogues complétés. *Vérif* : tests des traces en français ; `check`.

### Phase 5 — Les sujets

- **5.1** `subject.py` lit la traduction de l'exercice, `subject.<code>.txt` écrit et montré. *Vérif* : tests.
- **5.2** Les sujets en français (126 exercices). *Vérif* : chaque exercice a ses `$champs` et les textes de toutes ses valeurs ; chaque variant se rend dans chaque langue.
- **5.3** Les sujets des 7 autres langues, par exam. *Vérif* : idem, `check`.

### Phase 6 — 42pal online

- Reporter le système dans 42pal-online (même cœur, même interface). *Vérif* : ses tests.

## Risques

- **Le volume** : environ 7 600 mots de sujets par langue, plus 300 textes d'interface.
- **La qualité** : une erreur de traduction dans un sujet fausse l'exercice ; relecture humaine souhaitée.
- **La mise en page** : des textes plus longs peuvent casser l'alignement des menus ou déborder des cartes.
- **Reformuler l'anglais** invalide la traduction : `check` le signale, et le texte reste en anglais en attendant.

## Hors périmètre

- Le rapport d'issue, `check-catalog`, l'aide de `--help`.
- Les langues écrites de droite à gauche (le terminal les gère mal).
