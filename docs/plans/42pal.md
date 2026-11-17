# Plan — 42pal : réviser les exams 42 avec des variantes

## Objectif

Un outil pour les étudiants de 42 Mulhouse qui simule tous les exams (piscine et cursus, C, C++ et Python). Chaque sujet tiré est une **variante paramétrée** d'un modèle d'exo écrit sur le même thème que le vrai exam, et il est corrigé automatiquement.

- **Phase 1 (ce plan)** : un outil terminal qui reproduit l'examshell.
- **Phase 2 (plan séparé)** : une interface web, hébergée d'abord sur le VPS OVH, puis probablement sur un serveur de l'école.

**La phase 1 est finie quand** un étudiant du campus lance `./42pal` sans rien installer, passe un rank 02 complet avec des variantes qu'il n'a jamais vues, et que tout le catalogue passe `check-catalog`.

## Décisions

- **Langage** : Python 3.10 minimum (à confirmer sur un poste du campus), bibliothèque standard uniquement pour le cœur et les tests (`unittest`), car personne n'a le droit d'installer quoi que ce soit sur les postes.
- **Affichage** : `rich` (licence MIT) est embarqué dans `vendor/` avec `typing_extensions`, soit environ 1,2 Mo, sans `pygments` ni `markdown_it`. Il n'y a rien à installer et pas besoin de sudo. Seul `pal42/cli/` s'en sert : le cœur reste en bibliothèque standard, sans affichage. Vérifié sur le Python 3.10.12 du système, sans aucun paquet : console, couleurs, tableaux, panneaux, affichage en direct, prompt et barres de progression marchent.
- **Exo** : un modèle composé de paramètres (avec des combinaisons interdites possibles), d'un sujet à trous, d'un **oracle** Python, d'un générateur de tests, et d'une solution de référence `ref.c` paramétrée par `-D`.
- **Variante** : identifiée par `exo#seed`, donc reproductible.
- **Les exams pointent vers des thèmes.** Au tirage, on prend un thème du niveau, puis un modèle de ce thème, puis une seed.
- **Aucun sujet réel dans le dépôt.** Les sujets réels servent seulement à repérer les thèmes. Chaque modèle a son propre nom, son propre énoncé et ses propres exemples, et peut interdire la combinaison qui redonnerait le sujet réel.
- **Correction locale**, sur la machine de l'étudiant.
- **Compilation par défaut** : `cc -Wall -Wextra -Werror`, comme la moulinette.
- **Après un échec**, on retente le même sujet, avec une attente qui augmente à chaque échec.

## Structure visée

```
42pal/
├── 42pal                # script de lancement (python3 -m pal42)
├── pal42/               # le cœur, sans aucun affichage, réutilisé par le web
│   ├── model.py variant.py subject.py catalog.py
│   ├── grader.py trace.py harness.py checks.py exam.py session.py
│   ├── runners/         # base.py c.py cpp.py python.py
│   └── cli/             # shell.py practice.py check.py display.py
├── exercises/c/char_filter/   # exercise.py, ref.c
├── themes.json
├── exams/               # rank02.json, piscine_*.json
├── vendor/              # rich et typing_extensions, embarqués (rien à installer)
└── tests/
```

## Étapes

**Ordre de réalisation** : les étapes 1 à 8 sont faites. On fait ensuite l'interface d'abord (étapes 16 et 18), avec un `grademe` qui répond « pas encore branché », pour voir l'outil de bout en bout au plus tôt. Puis on reprend le correcteur (étapes 9 à 15), on le branche, et on continue avec les étapes 17, 19 et suivantes.

### Jalon 0 : squelette

**1. Initialiser le dépôt.** `git init`, `.gitignore`, le paquet `pal42/` avec `__main__.py` (option `--version`) et le script `./42pal`, qui marche depuis n'importe quel dossier. Lancer `python3 --version` sur un poste du campus pour fixer la version minimale.
- Vérifier : `./42pal --version` affiche la version, et `python3 -m unittest -v` passe.

### Jalon 1 : modèle d'exo et variantes

**2. Modèle de données.** `Param`, `Exercise` (langage, type programme ou fonction, fichiers attendus, fonctions autorisées, thèmes, paramètres, combinaisons interdites, sujet, oracle, tests) et `TestCase`, dans `pal42/model.py`.
- Test d'abord : un sujet qui utilise un paramètre inexistant lève une erreur dès la création de l'exo.

**3. Tirage d'une variante.** `draw(exo, seed)` renvoie une `Variant`. Le nom peut dépendre des paramètres. Fichier : `variant.py`.
- Test : la même seed donne la même variante.
- Test : sur 200 seeds, chaque valeur autorisée sort au moins une fois, et une combinaison interdite ne sort jamais.

**4. Sujet au format 42.** On produit les lignes Assignment name, Expected files et Allowed functions, une ligne de tirets, l'énoncé, puis les exemples `| cat -e` calculés par l'oracle. Fichier : `subject.py`.
- Test : l'en-tête suit bien le format 42.
- Test : un instantané de notre sujet, relu une fois à la main puis enregistré dans `tests/golden/`, ne change pas d'un lancement à l'autre.

**5. Premier modèle : `char_filter`**, un modèle original sur le thème « ensembles de caractères ». Paramètres : `mode` (communs, seulement dans le 1er, seulement dans le 2e), `ordre` et `séparateur`. La combinaison identique au sujet réel est interdite. Fichier : `exercises/c/char_filter/exercise.py`.
- Test : l'oracle donne les sorties de nos propres exemples, y compris pour un mauvais nombre d'arguments.

**6. Catalogue.** On découvre les exos dans `exercises/` et on les indexe par langage et par thème. Fichier : `catalog.py`.
- Test : `char_filter` est trouvé sous le thème `char_sets`.
- Test : un dossier sans `exercise.py` est ignoré avec un avertissement.

**7. Liste des thèmes : `themes.json`.** Pour chaque thème : son id, la compétence testée, et les exams et niveaux où il apparaît. Pour l'instant, seulement la piscine et le rank 02 : un premier jet écrit de mémoire (l'inventaire de 42_EXAM n'est plus en ligne), à faire relire par des étudiants qui ont passé ces exams.
- Test : un modèle qui cite un thème inconnu donne une erreur.
- Test : un thème sans compétence, sans exam ou avec un niveau qui n'est pas un nombre, ou un thème écrit deux fois, donne une erreur.

### Jalon 2 : correcteur C

**8. Compilation.** `cc -Wall -Wextra -Werror` dans un dossier temporaire, avec une commande configurable par exam. Fichiers : `runners/base.py` et `runners/c.py`.
- Test : un `.c` valide compile.
- Test : une variable inutilisée fait échouer la compilation, et l'erreur est capturée.

**9. Exécution.** On lance le programme avec des arguments ou une entrée standard, sous timeout, et on récupère stdout, le code de retour et le signal éventuel. L'entrée et la sortie passent par des fichiers temporaires, le programme tourne dans son propre groupe de processus, et tout le groupe est tué à la fin : aucun enfant lancé avec `fork()` ne reste en vie. La sortie est limitée à 1 Mo (au-delà, le système arrête le programme avec `SIGXFSZ`).
- Test : une boucle infinie donne TIMEOUT, et `*(volatile int *)0 = 0` donne SEGFAULT.
- Test : un enfant qui boucle est arrêté, que le programme finisse seul ou par timeout ; une sortie sans fin est coupée.

**10. Correcteur d'exos « programme ».** Chaque test compare la sortie à l'oracle, et on s'arrête au premier échec avec une **trace** comme celle de la moulinette : la commande du test, puis un diff en `cat -e` entre la sortie de l'étudiant (lignes `-`) et la sortie attendue (lignes `+`), et `Diff KO`. Un crash, un timeout ou une erreur de compilation donnent leur propre message à la place du diff. Le cœur renvoie le texte de la trace, et le shell l'écrit dans `traces/` (étape 18). Fichiers : `grader.py` et `trace.py`.

```
= Test 2 =======================================================================
$> ./repeat_twice "ab c" | cat -e
--- student
+++ moulinette
-ab c$
+ab c ab c$

Diff KO
```

- Test : une solution juste écrite par nous passe.
- Test : une solution sans `\n` échoue, et sa trace montre `-hello` contre `+hello$`, avec la commande du test.

**11. Exos « fonction ».** Un `main` de test est généré pour chaque variante. Le contrôle des fonctions interdites (étape 12, déjà faite) ne doit alors regarder que le code de l'étudiant, pas ce `main` de test (par exemple avec `nm -u` sur l'objet de l'étudiant seul). Fait : la compilation passe par des objets (`cc -c`), puis l'édition de liens avec le `main` de test. À améliorer : la trace d'une fonction affiche encore `$> ./ft_x args` au lieu de l'appel `ft_x("abc", 'a')`, et les exemples automatiques du sujet ne marchent que pour les programmes. Fichier : `harness.py`, avec un modèle « fonction » original sur le thème « parcours de chaîne ».
- Test : une fonction juste passe, une fonction décalée de 1 échoue.
- Test : un rendu qui contient un `main` donne une erreur claire.

**12. Fonctions interdites.** On liste les fonctions utilisées avec `nm -u` et on les compare aux fonctions autorisées. Fichier : `checks.py`.
- Test : `printf`, alors que seul `write` est autorisé, échoue avec « Forbidden function: printf ».

**13. Fuites mémoire (activable exo par exo).** Avec valgrind s'il est présent.
- Test : un malloc sans free échoue.
- Test : sans valgrind dans le PATH, on affiche un avertissement et rien ne plante.

### Jalon 3 : garantir que la correction est juste

**14. `ref.c` paramétrée.** Un seul fichier C avec des `#if MODE == …`, compilé avec `-D…` pour chaque variante. Fichier : `exercises/c/char_filter/ref.c`.
- Vérifier : il compile sans erreur sous `-Werror` pour toutes les combinaisons autorisées.

**15. Commande `./42pal check-catalog`.** Pour chaque exo, on teste toutes les combinaisons de paramètres (ou 50 seeds s'il y en a trop) en comparant `ref.c` et l'oracle sur tous les tests. Fichier : `cli/check.py`.
- Test : avec un oracle volontairement faux, la commande échoue en nommant `exo#seed` et le test.
- Test : sur le vrai catalogue, la commande passe.

### Jalon 4 : le mode exam en terminal

**16. Définition d'un exam.** Un fichier par exam (`exams/rank02.json`, `exams/piscine.json`) donne le titre, le langage, le nombre de niveaux, la durée et la commande de compilation ; les durées d'attente après un échec viendront à l'étape 19. Les thèmes de chaque niveau viennent de `themes.json`, pour ne pas les écrire deux fois. Un niveau dont aucun thème n'a encore de modèle est signalé par un avertissement et ne peut pas être joué. Au tirage : un thème du niveau, puis un modèle de ce thème, puis une seed. Fichier : `exam.py`.
- Test : le rank 02 a 4 niveaux, et `char_filter` est jouable au niveau 2.
- Test : un niveau sans aucun modèle donne un avertissement.
- Test : un fichier d'exam mal écrit donne une erreur dès le chargement.

**17. Session.** On garde l'exam, le niveau, le sujet en cours (`exo#seed`), le début de l'exam, les tentatives et l'heure de la prochaine correction possible dans `~/.42pal/session.json`, pour pouvoir reprendre. On garde aussi, à part, l'historique des exams terminés (exam, niveau atteint, note, tentatives, durée) : c'est la base du futur score (voir « Plus tard : gamification »). Fichier : `session.py`.
- Test : sauvegarder puis recharger donne le même état (l'horloge est injectée pour les tests).
- Test : un exam terminé s'ajoute à l'historique, qui survit à une nouvelle session.
- Fait : au lancement, « Resume your exam? … (y/n) » reprend le même sujet (`exo#seed`), au même niveau, avec le même mode, le temps ayant continué de courir ; `n` garde l'ancien exam dans l'historique comme « abandoned » ; un exam expiré pendant l'absence y va comme « time » sans question. Ctrl-C garde la session ; `finish`, Ctrl-D, la fin du temps ou l'exam réussi la terminent. Le chronomètre de l'exam ne repart plus de zéro à chaque niveau (bug corrigé au passage).

**18. Le shell examshell.** D'abord un faux login comme à l'exam : le login est prérempli avec le nom d'utilisateur, et le mot de passe est masqué, accepte n'importe quoi, n'est jamais vérifié ni gardé. Puis le choix de l'exam et du niveau de départ (parmi les niveaux jouables), et tout se passe dans `~/42pal_exam/` (pas `~/42pal`, qui est souvent le dépôt cloné), avec les commandes `status`, `grademe`, `finish` et `help`. Au tirage : un thème du niveau, puis un modèle, puis une seed. L'affichage passe par `rich` (couleurs, tableau des résultats, minuteur en direct), et le prompt utilise `readline` pour l'historique et la complétion des commandes. C'est à cette étape qu'on copie `rich` dans `vendor/` et que `./42pal` l'ajoute au chemin de Python. Fichiers : `cli/shell.py` et `cli/display.py`.

```
~/42pal_exam/
├── subjects/<exo>/subject.en.txt   le sujet tiré
├── rendu/<exo>/                    l'étudiant code ici
└── traces/                         une trace par grademe raté
```

`rendu/` est un simple dossier : `grademe` corrige les fichiers présents, commités ou non. Pour garder les réflexes du vrai exam, c'est aussi un dépôt git local relié à un dépôt nu caché dans `~/.42pal/rendu.git`, donc `git add`, `git commit` et `git push` marchent, sans être obligatoires. Si git manque, ce n'est qu'un dossier.

`grademe` affiche un spinner pendant la correction (« test 3/18 »), puis OK ou KO avec le chemin cliquable du journal (`traces/01_<nom>.trace`, écrit à chaque grademe), puis la trace elle-même dans le terminal, coupée après 25 lignes (entière dans le fichier).
- Vérifier à la main : une bonne solution fait passer au niveau suivant, une mauvaise écrit une trace dans `traces/`.
- Vérifier à la main : `git add . && git commit -m test && git push` marche dans `rendu/`.

**19. Temps et nouvel essai.** L'exam s'arrête à la durée maximale. Après un échec, on retente le même sujet, et l'attente avant le prochain `grademe` augmente à chaque échec. Fait : le premier nouvel essai est gratuit, puis l'attente suit le mode `soft` (0, 1, 2, 3, 5 min, par défaut) ou `hard` (0, 5, 10, 20, 40 min, avec `./42pal --hard`, choisi avant de lancer), réglable dans `retry_minutes` du fichier de l'exam ; l'attente repart de zéro après un sujet réussi. L'étudiant est prévenu : « If KO: next grademe in … » avant chaque correction, « Next grademe in … · if KO again: … » après un KO, et dans `status`. Fait aussi : l'exam s'arrête à la durée maximale (le temps est vérifié à chaque commande tapée : une commande trop tardive n'est pas exécutée, un `grademe` trop tardif n'est pas corrigé), avec un avertissement unique quand il reste moins de 10 minutes, et un résumé à la fin (niveaux réussis, `grademe` OK et KO, temps passé). Plus tard : un minuteur qui interrompt le prompt en direct.
- Test avec une horloge simulée : l'attente grandit d'un échec à l'autre, le sujet ne change pas, et l'exam se termine avec la note.

**20. Révision par thème.** `./42pal practice --theme <id>` enchaîne des variantes du même thème, sans timer. Fichier : `cli/practice.py`.
- Vérifier : 5 tirages donnent 5 seeds différentes, toutes du même thème.

**21. Installation au campus.** Un `README.md` (`git clone … && ./42pal`).
- Vérifier : sur un poste du campus, avec le `python3` du système, ça se lance sans pip ni sudo.

### Jalon 5 : remplir le catalogue

Chaque exo est une étape : un thème, un modèle original, sa `ref.c`, et `check-catalog` qui passe.

**22. Guide de contribution.** `CONTRIBUTING.md` et un dossier modèle `exercises/_template/`. La règle n°1 : décris le thème, écris ton propre nom, ton propre énoncé et tes propres exemples, et ne copie jamais un sujet réel.
- Vérifier : ajouter un deuxième modèle du thème `char_sets` en suivant uniquement le guide.

**23. Rank 02 jouable de bout en bout.** Un modèle par niveau d'abord, puis compléter les thèmes.
- Vérifier : un exam complet terminé à la main.

**24. Correcteur Python** (exos programme et fonction), dans `runners/python.py`. Il est d'abord testé sur un modèle simple d'un thème déjà connu. Les vrais modèles Python viendront quand les sujets auront été fournis.
- Test : une solution juste passe, une fausse échoue avec une trace.

**25. Correcteur C++** (`c++ -std=c++98 -Wall -Wextra -Werror`) et un premier modèle sur un thème du rank 05.

**26. Gros sujets** (thèmes shell et pipes, serveur réseau, printf, lecture ligne par ligne) : un sujet original par thème, avec peu ou pas de paramètres et un correcteur sur mesure. Un sujet par étape.

**27. Exams de la piscine** (`exams/piscine_*.json`), en réutilisant les thèmes C.

### Jalon 6 : web (plan séparé, après les premiers retours du campus)

FastAPI importe le même cœur. La correction tourne dans un conteneur Docker sans réseau, avec des limites de CPU, de mémoire et de processus, et un système de fichiers en lecture seule. On y ajoute un éditeur dans le navigateur, la connexion 42 et le suivi de la progression.

Le déploiement doit pouvoir changer de serveur : tout passe par Docker Compose et un fichier `.env`, sans rien de propre au VPS OVH. Passer au serveur de l'école reviendra à copier le compose et le `.env`.

### Plus tard : gamification (phase 2, seulement pour ceux qui le veulent)

Un score et des classements, **uniquement sur la base du volontariat** : c'est désactivé par défaut, on peut s'inscrire et se retirer à tout moment, et se retirer efface ses données du classement.

- **Score** : calculé à partir des exams terminés (niveau atteint, note, temps, nombre de tentatives) et des révisions par thème. La formule reste à définir.
- **Classements** : par promo (piscine ou année d'entrée en cursus), par campus et par exam. La promo et le campus viennent de la connexion 42.
- **Ce qui est visible** : le login (ou un pseudo), le score et le rang, jamais le code rendu.

**Ce qu'on prépare dès la phase 1**, pour ne pas tout refaire :
- La session (étape 17) garde l'historique des exams terminés, en local. Rien ne quitte la machine en phase 1.
- Le cœur renvoie les résultats sous forme de données (note, tentatives, durées) et non de texte, pour qu'on puisse les compter plus tard.
- Seules les corrections faites sur le serveur (jalon 6) compteront pour le classement : en local, l'étudiant peut modifier le correcteur, donc un score local n'est pas fiable.

## Risques

- **Un oracle faux donne des corrections fausses.** C'est le risque n°1. La parade est la double implémentation (oracle et `ref.c`), avec `check-catalog` obligatoire avant d'ajouter un exo.
- **Pas de sujets publics.** Le catalogue dépendra des thèmes que les étudiants décriront, d'où la liste des thèmes tôt (étape 7) et un guide de contribution clair (étape 22).
- **Une variante trop proche du sujet réel.** Les combinaisons interdites, et des noms et énoncés écrits par nous, limitent ce risque.
- **Une variante plus dure que son niveau.** Il faut garder des paramètres de même difficulté et relire chaque modèle.
- **La version de Python sur les postes du campus est inconnue.** On vise 3.10 et on vérifie dès l'étape 1.
- **valgrind peut manquer sur certains postes.** Dans ce cas, le contrôle des fuites est désactivé avec un avertissement.
- **Le cœur doit rester sans affichage**, sinon le web ne pourra pas s'y brancher.
- **Un classement pousse à tricher.** En local, le correcteur et l'oracle sont modifiables : seuls les exams corrigés sur le serveur comptent pour le classement.

## Questions ouvertes

- Sujets Python : à fournir plus tard, uniquement comme source de thèmes.
- Au vrai exam, après un échec, retente-t-on le même sujet ? C'est le comportement par défaut ici, et c'est réglable.
- Gamification : quelle formule de score ? Classement par login ou par pseudo ?

## Hors périmètre (phase 1)

- Le web, les comptes, la connexion 42, le score et le classement (phase 2, voir « Plus tard : gamification »).
- La génération de sujets par IA.
- L'anti-triche.
- Le support macOS testé (le vrai exam est sous Linux).
- La traduction des sujets.
