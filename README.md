# Droit français, sourcé

Recherche dans le droit français officiel (Légifrance open data de la DILA) où chaque affirmation est sourcée : article, identifiant Légifrance, lien et date de version.

- **Législation** : codes, lois, décrets et arrêtés consolidés avec toutes leurs versions datées (LEGI), Journal officiel tel que publié (JORF), conventions collectives (KALI).
- **Jurisprudence** : Conseil d'État et juridictions administratives (JADE), Cour de cassation (CASS, INCA), cours d'appel (CAPP), Conseil constitutionnel (CONSTIT), CNIL.

Le projet existe sous deux formes :

1. un **serveur MCP public** à ajouter dans Claude ou ChatGPT, sans rien installer ;
2. un **skill Claude Code** qui interroge des bases SQLite locales.

> **Information juridique, pas conseil.** Les réponses résument ce que disent les textes et les décisions de la base. La version qui fait foi est celle publiée sur [Légifrance](https://www.legifrance.gouv.fr). Pour un cas concret, consultez un avocat ou un professionnel du droit.

## En 30 secondes

Adresse du serveur : **`https://droit.studjoow.com/mcp`** (mise en ligne en cours)

### Dans Claude (claude.ai ou application de bureau)

1. Ouvrir **Paramètres**, puis **Connecteurs**.
2. Cliquer sur **Ajouter un connecteur personnalisé**.
3. Nom : `Droit français` ; URL : `https://droit.studjoow.com/mcp`. Pas d'authentification.
4. Dans une conversation, activer le connecteur (menu des outils) et poser la question : « Que dit l'article 1240 du Code civil ? ».

### Dans ChatGPT

1. Ouvrir **Paramètres**, puis **Applications et connecteurs** (selon l'offre, il faut activer le **mode développeur** dans les paramètres avancés).
2. **Créer** un connecteur : nom `Droit français`, URL `https://droit.studjoow.com/mcp`, authentification **aucune**.
3. Dans une conversation, choisir le connecteur dans le menu des outils.

### Limites honnêtes

- Serveur **gratuit, sans garantie** de disponibilité ni de résultat ; il peut être lent, limité ou arrêté.
- Limite de **60 requêtes par minute** par adresse IP.
- Base à jour du **<DATE_BASE>** (dumps DILA du 13/07/2025 plus les mises à jour quotidiennes). L'outil `etat_base` donne la date exacte du dernier incrément appliqué.
- Jurisprudence **non exhaustive** : seules les décisions diffusées par la DILA y figurent. Les cours d'appel (CAPP) s'arrêtent fin 2023. Environ 17 000 délibérations CNIL n'ont pas de texte (non communicables). Quelques dates aberrantes existent dans les sources (ex. 2999-01-01).
- **Information juridique, pas conseil.**

## Les outils du serveur

| Outil | Rôle |
|---|---|
| `lire_article` | Texte d'un article à une date donnée (« Code civil », « 1240 », « 2020-01-01 ») |
| `rechercher_loi` | Recherche plein texte dans LEGI, KALI, JORF ou tout |
| `lire_texte` | Fiche et plan d'un texte : identifiant, NOR, IDCC ou nom |
| `lister_codes` | Liste des codes |
| `rechercher_jurisprudence` | Recherche de décisions (mots, juridiction, numéro, ECLI, dates) |
| `lire_decision` | Texte intégral d'une décision |
| `verifier_references` | Contrôle qu'une référence existe et qu'une citation y figure mot pour mot |
| `etat_base` | Comptes et date de mise à jour de chaque base |

Le serveur impose un protocole de sourçage au modèle : chercher avant de répondre, croiser loi et jurisprudence, prendre la version à la date des faits, vérifier chaque référence, citer la source après chaque affirmation, terminer par un bloc « Sources », dire ce que la base ne contient pas.

## Skill Claude Code (bases locales)

```bash
git clone https://github.com/JohnJackHouzi/droit-francais-skill ~/.claude/skills/droit-francais
```

Il faut ensuite construire les bases (environ 30 Go au final, 40 Go libres pendant la construction) :

```bash
cd ~/.claude/skills/droit-francais
python3 -I scripts/install.py              # télécharge, construit, supprime les XML, base par base
python3 -I scripts/update_legi.py          # incrémentaux LEGI, JORF, KALI
python3 -I scripts/update_juri.py          # incrémentaux jurisprudence
python3 -I scripts/etat.py                 # état des bases
```

Les bases vont dans `~/droit-francais-data/` (variable `DROIT_DATA` pour changer). Aucune dépendance Python en dehors de la bibliothèque standard pour les scripts ; `SKILL.md` décrit le protocole de réponse et toutes les commandes.

## Héberger son propre serveur

```bash
docker compose up -d --build
curl http://localhost:8000/health     # 503 tant que les bases ne sont pas prêtes, 200 ensuite
```

Au premier démarrage, le conteneur télécharge les dumps DILA un par un dans le volume `/data`, les indexe, supprime archives et XML après chaque base et s'arrête si l'espace libre passe sous 15 Go. Prévoir **80 Go libres** (100 Go confortables) et quelques heures. Ensuite, les incrémentaux DILA sont appliqués chaque jour à 3 h UTC.

Pendant l'installation, `/health` et `/mcp` répondent 503 ; `/ping` répond toujours 200 (sonde de vie du conteneur).

Variables utiles :

| Variable | Défaut | Rôle |
|---|---|---|
| `DROIT_ALLOWED_HOSTS` | vide | Domaine(s) public(s) acceptés, ex. `droit.exemple.fr` (protection DNS rebinding) |
| `DROIT_RATE_PER_MIN` | 60 | Requêtes par minute et par IP |
| `DROIT_TRUSTED_PROXIES` | 1 | Nombre de proxys devant le serveur (IP lue dans `X-Forwarded-For`) |
| `DROIT_AUTO_INSTALL` | 1 | 0 : ne pas télécharger les dumps (bases envoyées par rsync) |
| `DROIT_AUTO_UPDATE` | 1 | 0 : pas de mise à jour quotidienne |
| `DROIT_UPDATE_HOUR_UTC` | 3 | Heure de la mise à jour quotidienne |
| `DROIT_MIN_FREE_GO` | 15 | Seuil d'arrêt de l'installation |

**Alternative à l'installation automatique** : construire les bases sur une autre machine puis les envoyer dans le volume, conteneur arrêté :

```bash
rsync -avP --inplace legi.sqlite juri.sqlite serveur:/chemin/du/volume/
```

puis démarrer avec `DROIT_AUTO_INSTALL=0`.

## Sources et licences

- Données : **DILA**, Légifrance open data (LEGI, JORF, KALI, JADE, CASS, CAPP, INCA, CONSTIT, CNIL), [echanges.dila.gouv.fr/OPENDATA](https://echanges.dila.gouv.fr/OPENDATA/), sous **Licence Ouverte 2.0** (Etalab). Les bases construites sont des données dérivées et restent soumises à cette licence ; elles ne sont pas incluses dans ce dépôt.
- Code : licence **MIT** (voir `LICENSE`).
- Ce projet n'est ni édité ni approuvé par la DILA ou Légifrance.
