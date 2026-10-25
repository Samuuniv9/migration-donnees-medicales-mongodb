// Création des comptes et des rôles, au tout premier démarrage de MongoDB.
// Ce script est lu par l'image officielle (dossier /docker-entrypoint-initdb.d)
// UNIQUEMENT si le volume de la base est vide.
// Les mots de passe viennent du fichier .env : ils ne sont jamais écrits ici.
// MongoDB ne stocke pas les mots de passe en clair : il garde une empreinte
// salée et hachée (mécanisme SCRAM-SHA-256).

const dbName = "healthcare";
const healthcare = db.getSiblingDB(dbName);

// 1. Administrateur des données : gère la base, ses collections et ses comptes.
healthcare.createUser({
  user: process.env.MONGO_ADMIN_USER,
  pwd: process.env.MONGO_ADMIN_PASSWORD,
  roles: [{ role: "dbOwner", db: dbName }],
});

// 2. Compte applicatif du script de migration : lire et écrire, rien d'autre.
healthcare.createUser({
  user: process.env.MONGO_APP_USER,
  pwd: process.env.MONGO_APP_PASSWORD,
  roles: [{ role: "readWrite", db: dbName }],
});

// 3. Analyste : lecture seule, pour les requêtes et les tableaux de bord.
healthcare.createUser({
  user: process.env.MONGO_ANALYST_USER,
  pwd: process.env.MONGO_ANALYST_PASSWORD,
  roles: [{ role: "read", db: dbName }],
});

print("Comptes créés : administrateur, migration, analyste.");
