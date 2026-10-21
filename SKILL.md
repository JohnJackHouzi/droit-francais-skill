---
name: droit-francais
description: Recherche dans le droit français officiel (Légifrance open data, DILA) en local : articles des codes à une date donnée, lois, décrets, JORF, conventions collectives (KALI), jurisprudence (Conseil d'État, Cour de cassation, cours d'appel, Conseil constitutionnel, CNIL). À utiliser dès qu'on demande ce que dit la loi, un article précis (« L1221-1 du Code du travail », « article 1240 du Code civil »), une décision, un numéro de pourvoi, une convention collective ou la version d'un texte à une date passée. Ne jamais répondre sur le droit français de mémoire quand ce skill est disponible.
---

# Droit français en local

Deux bases SQLite construites à partir des dumps officiels de la DILA (licence Ouverte 2.0), interrogées par des scripts Python sans dépendance.

| Base | Contenu |
|---|---|
| `legi.sqlite` | LEGI (codes, lois, décrets, arrêtés consolidés, toutes les versions d'article avec leurs dates), JORF, KALI |
| `juri.sqlite` | JADE (juridictions administratives), CASS, CAPP, INCA, CONSTIT, CNIL |
| `eu.sqlite` | Droit de l'UE en français (EUR-Lex via l'API Cellar) : règlements, directives, traités, Charte, arrêts de la CJUE et du Tribunal, selon le périmètre chargé |

Les bases sont dans `~/droit-francais-data/` (variable `DROIT_DATA` pour changer). Si elles manquent, voir « Installation » plus bas.

Les scripts sont dans `scripts/` à côté de ce fichier. Les lancer avec `python3 -I`.

## Législation

```bash
python3 -I scripts/search_legi.py article "Code civil" 1240
python3 -I scripts/search_legi.py article "Code du travail" L1221-1 --date 2020-01-01
python3 -I scripts/search_legi.py article "Code du travail" L1221-1 --versions
python3 -I scripts/search_legi.py recherche --q "préavis démission" --code "Code du travail"
python3 -I scripts/search_legi.py texte <id|NOR|IDCC|nom>
python3 -I scripts/search_legi.py textes <titre ou NOR>
python3 -I scripts/search_legi.py codes
python3 -I scripts/search_legi.py stats
```

Les numéros s'écrivent librement (`L1221-1`, `L. 1221-1`, `article 1240`).

## Jurisprudence

```bash
python3 -I scripts/search_juri.py --q "licenciement faute grave" --base cass --publie --tri date
python3 -I scripts/search_juri.py --numero 21-21.185
python3 -I scripts/search_juri.py --ecli ECLI:FR:...
python3 -I scripts/search_juri.py --q "principe de fraternité" --base constit
python3 -I scripts/search_juri.py --juridiction "conseil d'etat" --du 2020-01-01 --q "permis de construire"
python3 -I scripts/search_juri.py decision <id> --max-chars 20000
```

La syntaxe plein texte accepte `"phrase exacte"`, `AND`, `OR`, `NOT` et `prefixe*`. Les accents sont ignorés.

## Droit de l'Union européenne

```bash
python3 -I scripts/search_eu.py texte RGPD --article 17
python3 -I scripts/search_eu.py texte "règlement (UE) 2024/1689" --article 50
python3 -I scripts/search_eu.py texte C-131/12 --max-chars 20000
python3 -I scripts/search_eu.py recherche --q "droit à l'effacement" --type actes --celex RGPD
python3 -I scripts/search_eu.py recherche --q "transfert de données" --type jurisprudence --tri date
```

Références acceptées : CELEX (`32016R0679`), alias (`RGPD`, `RIA`, `DSA`, `DMA`, `TFUE`, `TUE`, `Charte`), « règlement (UE) 2016/679 », « directive 93/13/CEE », numéro d'affaire (`C-131/12`), ECLI. Les actes sont stockés dans leur dernière version consolidée (sans valeur officielle : la version qui fait foi est celle du JOUE). Citer avec le CELEX et le lien `https://eur-lex.europa.eu/legal-content/FR/TXT/?uri=CELEX:<id>`.

## Protocole de réponse (obligatoire, aucune exception)

Toute affirmation juridique doit être sourcée. Pas de source trouvée dans la base = pas d'affirmation.

1. **Chercher avant de répondre** : `search_legi.py` pour les textes, `search_juri.py` pour la jurisprudence. Pour une question de fond, croiser au moins la loi applicable ET la jurisprudence qui l'interprète. Lire le texte intégral de l'article (`article`, `texte`) et de la décision (`decision <id>`), pas seulement l'extrait de recherche.
2. **Version à la bonne date** : un article change. Utiliser `--date` pour la date des faits quand elle est connue, et signaler quand la version en vigueur aujourd'hui diffère. Contrôler l'état (VIGUEUR, MODIFIE, ABROGE).
3. **Vérifier chaque référence avant de la citer** :
   ```bash
   python3 -I scripts/verify.py "Code du travail L1221-1" "21-21.185" --date 2024-05-01
   python3 -I scripts/verify.py "Code civil 1240" --quote "Tout fait quelconque de l'homme"
   python3 -I scripts/verify.py "RGPD art. 17" "C-131/12"
   ```
   Une ligne `[INTROUVABLE]` ou une citation `ABSENTE` interdit de citer la référence telle quelle : la corriger ou la retirer. Les citations entre guillemets doivent être copiées du texte lu dans la base, jamais reconstituées.
4. **Format des citations** : dans le corps de la réponse, la source suit immédiatement l'affirmation, sous la forme `(Code du travail, art. L1237-1)` ou `(Cass. soc., 12 juillet 2023, n° 21-21.185)`. Jamais d'affirmation de droit sans référence à côté.
5. **Bloc « Sources » final** (toujours présent), une ligne par référence, reprise de la sortie de `verify.py` :
   `Code civil, art. 1240 (version du 2016-10-01 à ce jour, VIGUEUR) [LEGIARTI000032041571] https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000032041571`
   `RGPD, art. 17 (version consolidée au 2016-05-04) [CELEX 32016R0679] https://eur-lex.europa.eu/legal-content/FR/TXT/?uri=CELEX:32016R0679`
6. **Dire ce qu'on ne sait pas** : si la base ne contient pas la réponse, ou si elle exige une appréciation de fait, l'écrire explicitement plutôt que combler de mémoire. Séparer clairement ce que dit le texte (cité) de l'interprétation proposée (signalée comme telle).
7. **Date de la base** : les dumps datent du 13/07/2025 plus les incrémentaux appliqués ; `python3 -I scripts/etat.py` donne le dernier incrément de chaque base. Annoncer cette date quand la question dépend de l'actualité du droit, et proposer `update_legi.py` / `update_juri.py` si la base est ancienne.
8. **Information juridique, pas conseil** : résumer ce que dit le texte, renvoyer vers Légifrance pour la version faisant foi et vers un avocat pour un cas concret.
9. **Limites connues** : les cours d'appel (CAPP) s'arrêtent fin 2023 ; une partie des délibérations CNIL n'a pas de texte (non communicable) ; seules les décisions diffusées par la DILA existent, la jurisprudence n'est donc pas exhaustive.

## Mise à jour

```bash
python3 -I scripts/update_legi.py            # applique les incrémentaux LEGI/JORF/KALI
python3 -I scripts/update_juri.py            # applique les incrémentaux jurisprudence
```

La reprise se fait à partir du dernier incrémental appliqué. La suppression des textes retirés par la DILA n'a pas été validée sur de vraies données.

## Installation (première fois)

Prévoir environ 40 Go libres le temps de la construction (les XML décompressés sont supprimés ensuite) et environ 30 Go pour les deux bases finales.

```bash
python3 -I scripts/install.py                # toutes les bases DILA, une par une
python3 -I scripts/install.py --bases constit,cnil,kali   # sous-ensemble
python3 -I scripts/build_eu.py               # droit de l'UE, périmètre de départ (quelques Mo)
python3 -I scripts/build_eu.py --chiffrer    # estimer avant --actes-en-vigueur ou --cjue
python3 -I scripts/etat.py                   # état des bases
```

`install.py` télécharge chaque dump global depuis `https://echanges.dila.gouv.fr/OPENDATA/<BASE>/`, l'extrait, l'indexe, puis supprime archive et XML avant la base suivante ; il s'arrête si l'espace libre passe sous 15 Go (`DROIT_MIN_FREE_GO`). Une base déjà construite est sautée.
