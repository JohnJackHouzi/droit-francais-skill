import re
import unicodedata

# Chaque obligation : (outil, arguments, intitulé, ce qu'il faut vérifier dans le projet).
# Toutes les références ont été contrôlées dans les bases (verify.py) avant d'être listées ici.

CONSO = "Code de la consommation"

DOMAINES = [
    ("site", "Site ou application en ligne",
     ["site", "application", "appli", "app ", "plateforme", "en ligne", "web", "internet", "boutique"],
     [("lire_article", {"code": "LEGITEXT000005789847", "numero": "1-1"}, "LCEN, art. 1-1 : mentions légales",
       "Les mentions d'identification de l'éditeur, du directeur de la publication et de l'hébergeur sont-elles accessibles ?"),
      ("lire_article", {"code": "LEGITEXT000005616341", "numero": "2"}, "Loi n° 94-665, art. 2 : emploi du français",
       "L'offre, la présentation et les conditions sont-elles rédigées en français pour le public français ?"),
      ("rechercher_loi", {"requete": "accessibles aux personnes handicapées services de communication au public en ligne"},
       "Décret n° 2019-768 : accessibilité numérique",
       "Le service entre-t-il dans le champ des obligations d'accessibilité (taille de l'entreprise, secteur) ?")]),
    ("donnees", "Données personnelles (RGPD)",
     ["donnee", "compte", "inscription", "email", "mail", "formulaire", "client", "utilisateur", "photo", "adresse",
      "telephone", "crm", "fichier", "commande", "paiement", "prenom", "nom "],
     [("lire_texte_ue", {"reference": "RGPD", "article": "5"}, "RGPD, art. 5 : principes (minimisation, durée de conservation)",
       "Les données collectées sont-elles limitées au nécessaire, avec une durée de conservation définie ?"),
      ("lire_texte_ue", {"reference": "RGPD", "article": "6"}, "RGPD, art. 6 : base légale",
       "Chaque traitement a-t-il une base légale identifiée (contrat, consentement, intérêt légitime...) ?"),
      ("lire_texte_ue", {"reference": "RGPD", "article": "13"}, "RGPD, art. 13 : information des personnes",
       "Une politique de confidentialité informe-t-elle des finalités, destinataires, durées et droits ?"),
      ("lire_texte_ue", {"reference": "RGPD", "article": "28"}, "RGPD, art. 28 : sous-traitants",
       "Les prestataires qui traitent des données (hébergeur, e-mails, paiement, CRM, IA) sont-ils liés par un contrat conforme ?"),
      ("lire_texte_ue", {"reference": "RGPD", "article": "30"}, "RGPD, art. 30 : registre des traitements",
       "Un registre des activités de traitement est-il tenu ?"),
      ("lire_texte_ue", {"reference": "RGPD", "article": "32"}, "RGPD, art. 32 : sécurité",
       "Les mesures de sécurité (accès, chiffrement, sauvegardes) sont-elles adaptées au risque ?"),
      ("lire_texte_ue", {"reference": "RGPD", "article": "33"}, "RGPD, art. 33 : violation de données",
       "Une procédure de notification en 72 heures est-elle prévue ?")]),
    ("transferts", "Transferts de données hors de l'UE",
     ["etats-unis", "usa", "americain", "openai", "chatgpt", "google", "aws", "amazon", "vercel", "stripe", "resend",
      "hubspot", "meta", "facebook", "microsoft", "cloudflare", "anthropic"],
     [("lire_texte_ue", {"reference": "RGPD", "article": "44"}, "RGPD, art. 44 : transferts hors UE",
       "Les prestataires hors UE reposent-ils sur un mécanisme valable (décision d'adéquation, clauses types) ?")]),
    ("cookies", "Cookies et traceurs",
     ["cookie", "analytics", "tracking", "traceur", "pixel", "ga4", "publicite", "remarketing", "tag manager", "hotjar", "clarity"],
     [("lire_article", {"code": "LEGITEXT000006068624", "numero": "82"}, "Loi Informatique et libertés, art. 82 : cookies",
       "Les traceurs non essentiels sont-ils déposés seulement après consentement, avec refus aussi simple qu'accepter ?")]),
    ("mineurs", "Public mineur",
     ["enfant", "mineur", "ecole", "eleve", "adolescent", "ado ", "bebe", "naissance", "college", "lycee"],
     [("lire_texte_ue", {"reference": "RGPD", "article": "8"}, "RGPD, art. 8 : consentement des mineurs",
       "Si des enfants sont concernés, le consentement parental est-il recueilli quand il est requis ?")]),
    ("vente", "Vente en ligne aux consommateurs",
     ["vente", "vendre", "boutique", "e-commerce", "ecommerce", "commande", "panier", "paiement", "stripe", "prix",
      "achat", "acheter", "tarif", "checkout", "client"],
     [("lire_article", {"code": CONSO, "numero": "L111-1"}, "C. conso., art. L111-1 : information précontractuelle",
       "Caractéristiques essentielles, prix, délai de livraison et identité du vendeur sont-ils affichés avant la commande ?"),
      ("lire_article", {"code": CONSO, "numero": "L112-1"}, "C. conso., art. L112-1 : affichage des prix",
       "Les prix sont-ils affichés clairement, frais compris ?"),
      ("lire_article", {"code": CONSO, "numero": "L221-5"}, "C. conso., art. L221-5 : informations des contrats à distance",
       "Les informations sur le droit de rétractation et son formulaire sont-elles fournies ?"),
      ("lire_article", {"code": CONSO, "numero": "L221-14"}, "C. conso., art. L221-14 : bouton de commande",
       "Le bouton final indique-t-il clairement une obligation de paiement ?"),
      ("lire_article", {"code": CONSO, "numero": "L221-18"}, "C. conso., art. L221-18 : délai de rétractation",
       "Le délai de 14 jours est-il respecté, ou une exception s'applique-t-elle ?"),
      ("lire_article", {"code": CONSO, "numero": "L612-1"}, "C. conso., art. L612-1 : médiation",
       "Un médiateur de la consommation est-il désigné ?"),
      ("lire_article", {"code": CONSO, "numero": "L616-1"}, "C. conso., art. L616-1 : information sur la médiation",
       "Les coordonnées du médiateur figurent-elles sur le site et dans les CGV ?")]),
    ("personnalise", "Produits personnalisés ou sur mesure",
     ["personnalis", "sur mesure", "unique", "prenom", "a votre image", "custom"],
     [("lire_article", {"code": CONSO, "numero": "L221-28"}, "C. conso., art. L221-28 : exceptions au droit de rétractation",
       "L'exclusion de la rétractation pour un bien « nettement personnalisé » (3°) est-elle correctement annoncée ?")]),
    ("abonnement", "Abonnements et paiements récurrents",
     ["abonnement", "mensuel", "annuel", "recurrent", "renouvel", "resiliation", "sans engagement"],
     [("lire_article", {"code": CONSO, "numero": "L215-1"}, "C. conso., art. L215-1 : reconduction tacite",
       "Le consommateur est-il prévenu de la possibilité de ne pas reconduire un contrat à durée déterminée ?"),
      ("lire_article", {"code": CONSO, "numero": "L215-1-1"}, "C. conso., art. L215-1-1 : résiliation en ligne",
       "Une fonctionnalité de résiliation en ligne, simple et accessible, est-elle proposée ?"),
      ("lire_article", {"code": CONSO, "numero": "L221-25"}, "C. conso., art. L221-25 : exécution avant la fin du délai de rétractation",
       "La demande expresse d'exécution immédiate est-elle recueillie, avec ses conséquences ?")]),
    ("biens", "Biens livrés",
     ["livraison", "livre", "imprime", "colis", "expedition", "produit", "objet", "jeu ", "carte", "boite", "envoi"],
     [("lire_article", {"code": CONSO, "numero": "L216-1"}, "C. conso., art. L216-1 : délai de livraison",
       "Un délai ou une date de livraison est-il indiqué ?"),
      ("lire_article", {"code": CONSO, "numero": "L217-3"}, "C. conso., art. L217-3 : garantie légale de conformité",
       "La garantie légale de conformité est-elle mentionnée et honorée ?")]),
    ("livre", "Édition et vente de livres",
     ["livre", "edition", "editeur", "ouvrage", "album", "roman"],
     [("lire_article", {"code": "LEGITEXT000006068716", "numero": "1"}, "Loi n° 81-766, art. 1 : prix unique du livre",
       "Le prix de vente au public est-il fixé par l'éditeur et respecté ? Le livre personnalisé entre-t-il dans le champ ?")]),
    ("prospection", "Prospection et e-mails marketing",
     ["newsletter", "emailing", "prospection", "relance", "sms", "marketing", "campagne", "panier abandonne"],
     [("lire_article", {"code": "Code des postes et des communications électroniques", "numero": "L34-5"},
       "CPCE, art. L34-5 : prospection électronique",
       "Le consentement préalable est-il recueilli (ou l'exception client pour des produits analogues) avec un lien de désinscription ?")]),
    ("ia", "Intelligence artificielle",
     ["ia ", " ia", "intelligence artificielle", "chatbot", "gpt", "openai", "claude", "llm", "generat", "genere",
      "modele", "midjourney", "dall", "deepfake", "automatis"],
     [("lire_texte_ue", {"reference": "RIA", "article": "5"}, "Règlement IA, art. 5 : pratiques interdites",
       "Le système n'utilise-t-il aucune pratique interdite (manipulation, notation sociale, etc.) ?"),
      ("lire_texte_ue", {"reference": "RIA", "article": "50"}, "Règlement IA, art. 50 : transparence",
       "Les utilisateurs sont-ils informés qu'ils interagissent avec une IA, et les contenus générés sont-ils signalés ?"),
      ("lire_texte_ue", {"reference": "RIA", "article": "4"}, "Règlement IA, art. 4 : maîtrise de l'IA",
       "Les personnes qui utilisent ou supervisent l'IA ont-elles un niveau de connaissance suffisant ?"),
      ("lire_texte_ue", {"reference": "RIA", "article": "6"}, "Règlement IA, art. 6 : systèmes à haut risque",
       "Le cas d'usage figure-t-il parmi les systèmes à haut risque (annexe III : emploi, éducation, crédit...) ?")]),
    ("contenus", "Contenus publiés par les utilisateurs",
     ["avis", "commentaire", "upload", "televers", "marketplace", "communaute", "forum", "publier", "partage", "galerie"],
     [("lire_texte_ue", {"reference": "DSA", "article": "14"}, "DSA, art. 14 : conditions générales",
       "Les restrictions de contenus et leur modération sont-elles décrites dans les conditions d'utilisation ?"),
      ("lire_texte_ue", {"reference": "DSA", "article": "16"}, "DSA, art. 16 : signalement de contenus",
       "Un mécanisme de notification de contenus illicites est-il en place ?"),
      ("lire_texte_ue", {"reference": "DSA", "article": "17"}, "DSA, art. 17 : motivation des décisions",
       "Les retraits de contenus sont-ils motivés auprès de l'utilisateur ?")]),
    ("images", "Images, photos et droits d'auteur",
     ["photo", "image", "illustration", "dessin", "musique", "video", "portrait", "visage", "contenu"],
     [("lire_article", {"code": "Code civil", "numero": "9"}, "Code civil, art. 9 : droit à l'image et vie privée",
       "Les personnes photographiées ou représentées ont-elles donné leur accord ?"),
      ("lire_article", {"code": "Code de la propriété intellectuelle", "numero": "L122-4"}, "CPI, art. L122-4 : reproduction",
       "Les images, polices, musiques et textes utilisés sont-ils libres de droits ou sous licence ?"),
      ("lire_article", {"code": "Code de la propriété intellectuelle", "numero": "L111-1"}, "CPI, art. L111-1 : droit d'auteur",
       "À qui appartiennent les créations livrées (auteur, illustrateur, IA) et le contrat le prévoit-il ?")]),
    ("b2b", "Ventes entre professionnels",
     ["b2b", "entreprise", "professionnel", "facture", "devis", "comite d'entreprise", "cse", "grossiste", "revendeur"],
     [("lire_article", {"code": "Code de commerce", "numero": "L441-9"}, "C. com., art. L441-9 : mentions des factures",
       "Les factures portent-elles les mentions obligatoires ? Attention : version abrogée au 01/01/2027, vérifier le texte qui la remplace."),
      ("lire_article", {"code": "Code de commerce", "numero": "L441-10"}, "C. com., art. L441-10 : délais de paiement et pénalités",
       "Délais de paiement, pénalités de retard et indemnité de 40 € figurent-ils ? Abrogé au 01/01/2027 : vérifier le texte suivant.")]),
]

PAR_CLE = {d[0]: d for d in DOMAINES}


def _normaliser(texte):
    t = unicodedata.normalize("NFD", texte.lower())
    return " " + re.sub(r"\s+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn")) + " "


def detecter(description, forces=()):
    t = _normaliser(description)
    trouves = []
    for cle, titre, mots, obligations in DOMAINES:
        indices = sorted({m.strip() for m in mots if m in t})
        if indices or cle in forces:
            trouves.append((cle, titre, indices or ["demandé"], obligations))
    return trouves


def _appel(outil, args):
    return "%s(%s)" % (outil, ", ".join('%s="%s"' % (k, v) for k, v in args.items()))


def analyser(description, domaines=""):
    forces = {d.strip() for d in domaines.split(",") if d.strip() in PAR_CLE}
    trouves = detecter(description, forces)
    absents = [d for d in DOMAINES if d[0] not in {t[0] for t in trouves}]
    lignes = [
        "PRÉ-ANALYSE DE CONFORMITÉ (France et Union européenne)",
        "Information juridique, pas un avis : cette liste aide à repérer les obligations probables ; elle ne certifie "
        "aucune conformité. Pour une décision, consulter un avocat.",
        "",
        "Domaines détectés dans la description : %d sur %d." % (len(trouves), len(DOMAINES)),
    ]
    n = 0
    for cle, titre, indices, obligations in trouves:
        lignes += ["", "## %s [%s] (indices : %s)" % (titre, cle, ", ".join(indices))]
        for outil, args, intitule, question in obligations:
            n += 1
            lignes.append("%d. %s\n   À vérifier : %s\n   Lire : %s" % (n, intitule, question, _appel(outil, args)))
    if absents:
        lignes += ["", "Domaines non détectés (à ajouter avec le paramètre domaines si le projet est concerné) : "
                   + ", ".join("%s (%s)" % (d[0], d[1]) for d in absents)]
    lignes += [
        "",
        "MÉTHODE OBLIGATOIRE POUR RÉDIGER LE RAPPORT",
        "1. Lire chaque texte listé avec l'outil indiqué : ne jamais résumer un article de mémoire.",
        "2. Pour chaque point, classer : CONFORME EN APPARENCE, MANQUANT, ou À VÉRIFIER (information insuffisante). "
        "Si la description ne dit rien, c'est À VÉRIFIER, jamais CONFORME.",
        "3. Chaque constat cite son article et l'extrait utile, copié du texte lu.",
        "4. Chercher la jurisprudence ou les sanctions seulement pour les points MANQUANTS importants.",
        "5. Contrôler toutes les références avec verifier_references avant de les citer.",
        "6. Terminer par : les 5 priorités à corriger, les questions à poser à un avocat, puis le bloc Sources.",
    ]
    return "\n".join(lignes)


def toutes_les_obligations():
    for cle, titre, mots, obligations in DOMAINES:
        for outil, args, intitule, question in obligations:
            yield cle, outil, args, intitule
