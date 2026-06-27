#!/usr/bin/env python3
"""
translate_locales.py — populate frontend/messages/<locale>.json with proper
translations for the core UI strings.

This replaces the English seed for the *core* keys (common, nav, auth,
errors, success, onboarding) in every locale file that currently contains a
copy of en.json. Non-core keys are left in English so English acts as a
safe fallback until a full translation pass is done.

Strategy: the dictionary below is authored by hand per language for the
highest-visibility strings. For any key not present in the dictionary the
English source is kept. Idempotent — safe to re-run.

Run from repo root:  python3 scripts/translate_locales.py
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MSGS = ROOT / "frontend" / "messages"

# Locale code → translations for the core UI strings.
# Keys use dotted paths matching en.json structure.
T: dict[str, dict[str, str]] = {
    # ─── Nordic ────────────────────────────────────────────────────────────
    "sv": {
        "common.loading": "Laddar...", "common.error": "Något gick fel",
        "common.save": "Spara", "common.cancel": "Avbryt", "common.delete": "Radera",
        "common.edit": "Redigera", "common.create": "Skapa", "common.search": "Sök...",
        "common.noResults": "Inga resultat", "common.back": "Tillbaka",
        "nav.dashboard": "Översikt", "nav.analytics": "Analys", "nav.aiAdvisor": "AI-rådgivare",
        "nav.inventory": "Lager", "nav.invoices": "Fakturor", "nav.recurring": "Återkommande",
        "nav.cashRegister": "Kassa", "nav.customers": "Kunder", "nav.settings": "Inställningar",
        "nav.signOut": "Logga ut",
        "auth.login": "Logga in", "auth.signup": "Registrera", "auth.email": "E-postadress",
        "auth.password": "Lösenord", "auth.forgotPassword": "Glömt lösenord?",
        "auth.signInWithPassword": "Logga in", "auth.createAccount": "Skapa konto",
        "auth.noAccount": "Har du inget konto?", "auth.hasAccount": "Har du redan ett konto?",
        "errors.invalidCredentials": "Fel e-post eller lösenord.",
        "errors.networkError": "Anslutningsfel. Kontrollera din internetanslutning.",
        "errors.sessionExpired": "Din session har gått ut. Logga in igen.",
        "errors.unauthorized": "Du har inte behörighet till detta.",
        "errors.serverError": "Något gick fel på vår sida.",
        "errors.notFound": "Sidan finns inte.",
        "success.loggedIn": "Välkommen tillbaka!", "success.loggedOut": "Du är utloggad.",
    },
    "no": {
        "common.loading": "Laster...", "common.error": "Noe gikk galt",
        "common.save": "Lagre", "common.cancel": "Avbryt", "common.delete": "Slett",
        "common.edit": "Rediger", "common.create": "Opprett", "common.search": "Søk...",
        "common.noResults": "Ingen resultater", "common.back": "Tilbake",
        "nav.dashboard": "Oversikt", "nav.analytics": "Analyse", "nav.aiAdvisor": "AI-rådgiver",
        "nav.inventory": "Lager", "nav.invoices": "Fakturaer", "nav.recurring": "Gjentakende",
        "nav.cashRegister": "Kasse", "nav.customers": "Kunder", "nav.settings": "Innstillinger",
        "nav.signOut": "Logg ut",
        "auth.login": "Logg inn", "auth.signup": "Registrer", "auth.email": "E-postadresse",
        "auth.password": "Passord", "auth.forgotPassword": "Glemt passord?",
        "auth.signInWithPassword": "Logg inn", "auth.createAccount": "Opprett konto",
        "auth.noAccount": "Har du ikke en konto?", "auth.hasAccount": "Har du allerede en konto?",
        "errors.invalidCredentials": "Feil e-post eller passord.",
        "errors.networkError": "Tilkoblingsfeil. Sjekk internett.",
        "errors.sessionExpired": "Økten er utløpt. Logg inn igjen.",
        "errors.unauthorized": "Du har ikke tillatelse.",
        "errors.serverError": "Noe gikk galt hos oss.",
        "errors.notFound": "Siden finnes ikke.",
        "success.loggedIn": "Velkommen tilbake!", "success.loggedOut": "Du er logget ut.",
    },
    "da": {
        "common.loading": "Indlæser...", "common.error": "Noget gik galt",
        "common.save": "Gem", "common.cancel": "Annuller", "common.delete": "Slet",
        "common.edit": "Rediger", "common.create": "Opret", "common.search": "Søg...",
        "common.noResults": "Ingen resultater", "common.back": "Tilbage",
        "nav.dashboard": "Oversigt", "nav.analytics": "Analyse", "nav.aiAdvisor": "AI-rådgiver",
        "nav.inventory": "Lager", "nav.invoices": "Fakturaer", "nav.recurring": "Tilbagevendende",
        "nav.cashRegister": "Kasse", "nav.customers": "Kunder", "nav.settings": "Indstillinger",
        "nav.signOut": "Log ud",
        "auth.login": "Log ind", "auth.signup": "Tilmeld", "auth.email": "E-mailadresse",
        "auth.password": "Adgangskode", "auth.forgotPassword": "Glemt adgangskode?",
        "auth.signInWithPassword": "Log ind", "auth.createAccount": "Opret konto",
        "auth.noAccount": "Har du ingen konto?", "auth.hasAccount": "Har du allerede en konto?",
        "errors.invalidCredentials": "Forkert e-mail eller adgangskode.",
        "errors.networkError": "Forbindelsesfejl. Tjek dit internet.",
        "errors.sessionExpired": "Din session er udløbet. Log ind igen.",
        "errors.unauthorized": "Du har ikke tilladelse.",
        "errors.serverError": "Noget gik galt hos os.",
        "errors.notFound": "Siden findes ikke.",
        "success.loggedIn": "Velkommen tilbage!", "success.loggedOut": "Du er logget ud.",
    },
    "fi": {
        "common.loading": "Ladataan...", "common.error": "Jokin meni vikaan",
        "common.save": "Tallenna", "common.cancel": "Peruuta", "common.delete": "Poista",
        "common.edit": "Muokkaa", "common.create": "Luo", "common.search": "Etsi...",
        "common.noResults": "Ei tuloksia", "common.back": "Takaisin",
        "nav.dashboard": "Kojelauta", "nav.analytics": "Analytiikka", "nav.aiAdvisor": "AI-neuvoja",
        "nav.inventory": "Varasto", "nav.invoices": "Laskut", "nav.recurring": "Toistuvat",
        "nav.cashRegister": "Kassa", "nav.customers": "Asiakkaat", "nav.settings": "Asetukset",
        "nav.signOut": "Kirjaudu ulos",
        "auth.login": "Kirjaudu", "auth.signup": "Rekisteröidy", "auth.email": "Sähköposti",
        "auth.password": "Salasana", "auth.forgotPassword": "Unohditko salasanan?",
        "auth.signInWithPassword": "Kirjaudu sisään", "auth.createAccount": "Luo tili",
        "auth.noAccount": "Eikö sinulla ole tiliä?", "auth.hasAccount": "Onko sinulla jo tili?",
        "errors.invalidCredentials": "Virheellinen sähköposti tai salasana.",
        "errors.networkError": "Yhteysvirhe.",
        "errors.sessionExpired": "Istunto päättyi.",
        "errors.unauthorized": "Ei oikeuksia.",
        "errors.serverError": "Palvelinvirhe.",
        "errors.notFound": "Sivua ei löydy.",
        "success.loggedIn": "Tervetuloa takaisin!", "success.loggedOut": "Olet kirjautunut ulos.",
    },
    "is": {
        "common.loading": "Hleður...", "common.error": "Eitthvað fór úrskeiðis",
        "common.save": "Vista", "common.cancel": "Hætta við", "common.delete": "Eyða",
        "common.edit": "Breyta", "common.create": "Búa til", "common.search": "Leita...",
        "common.noResults": "Engar niðurstöður", "common.back": "Til baka",
        "nav.dashboard": "Yfirlit", "nav.analytics": "Greining", "nav.aiAdvisor": "AI-ráðgjafi",
        "nav.inventory": "Lager", "nav.invoices": "Reikningar", "nav.recurring": "Endurtekin",
        "nav.cashRegister": "Kassi", "nav.customers": "Viðskiptavinir", "nav.settings": "Stillingar",
        "nav.signOut": "Skrá út",
        "auth.login": "Skrá inn", "auth.signup": "Skrá", "auth.email": "Netfang",
        "auth.password": "Lykilorð",
        "success.loggedIn": "Velkomin aftur!", "success.loggedOut": "Þú hefur skráð þig út.",
    },

    # ─── Western Europe ────────────────────────────────────────────────────
    "de": {
        "common.loading": "Wird geladen...", "common.error": "Ein Fehler ist aufgetreten",
        "common.save": "Speichern", "common.cancel": "Abbrechen", "common.delete": "Löschen",
        "common.edit": "Bearbeiten", "common.create": "Erstellen", "common.search": "Suchen...",
        "common.noResults": "Keine Ergebnisse", "common.back": "Zurück",
        "nav.dashboard": "Übersicht", "nav.analytics": "Analyse", "nav.aiAdvisor": "KI-Berater",
        "nav.inventory": "Lager", "nav.invoices": "Rechnungen", "nav.recurring": "Wiederkehrend",
        "nav.cashRegister": "Kasse", "nav.customers": "Kunden", "nav.settings": "Einstellungen",
        "nav.signOut": "Abmelden",
        "auth.login": "Anmelden", "auth.signup": "Registrieren", "auth.email": "E-Mail-Adresse",
        "auth.password": "Passwort", "auth.forgotPassword": "Passwort vergessen?",
        "auth.signInWithPassword": "Anmelden", "auth.createAccount": "Konto erstellen",
        "auth.noAccount": "Noch kein Konto?", "auth.hasAccount": "Haben Sie bereits ein Konto?",
        "errors.invalidCredentials": "Falsche E-Mail oder Passwort.",
        "errors.networkError": "Verbindungsfehler.",
        "errors.sessionExpired": "Sitzung abgelaufen.",
        "errors.unauthorized": "Keine Berechtigung.",
        "errors.serverError": "Serverfehler.",
        "errors.notFound": "Seite nicht gefunden.",
        "success.loggedIn": "Willkommen zurück!", "success.loggedOut": "Sie wurden abgemeldet.",
    },
    "fr": {
        "common.loading": "Chargement...", "common.error": "Une erreur s'est produite",
        "common.save": "Enregistrer", "common.cancel": "Annuler", "common.delete": "Supprimer",
        "common.edit": "Modifier", "common.create": "Créer", "common.search": "Rechercher...",
        "common.noResults": "Aucun résultat", "common.back": "Retour",
        "nav.dashboard": "Tableau de bord", "nav.analytics": "Analytique", "nav.aiAdvisor": "Conseiller IA",
        "nav.inventory": "Stock", "nav.invoices": "Factures", "nav.recurring": "Récurrent",
        "nav.cashRegister": "Caisse", "nav.customers": "Clients", "nav.settings": "Paramètres",
        "nav.signOut": "Déconnexion",
        "auth.login": "Se connecter", "auth.signup": "S'inscrire", "auth.email": "Adresse e-mail",
        "auth.password": "Mot de passe", "auth.forgotPassword": "Mot de passe oublié ?",
        "auth.signInWithPassword": "Se connecter", "auth.createAccount": "Créer un compte",
        "auth.noAccount": "Pas encore de compte ?", "auth.hasAccount": "Vous avez déjà un compte ?",
        "errors.invalidCredentials": "E-mail ou mot de passe incorrect.",
        "errors.networkError": "Erreur de connexion.",
        "errors.sessionExpired": "Session expirée.",
        "errors.unauthorized": "Non autorisé.",
        "errors.serverError": "Erreur serveur.",
        "errors.notFound": "Page introuvable.",
        "success.loggedIn": "Bon retour !", "success.loggedOut": "Vous êtes déconnecté.",
    },
    "es": {
        "common.loading": "Cargando...", "common.error": "Algo salió mal",
        "common.save": "Guardar", "common.cancel": "Cancelar", "common.delete": "Eliminar",
        "common.edit": "Editar", "common.create": "Crear", "common.search": "Buscar...",
        "common.noResults": "Sin resultados", "common.back": "Volver",
        "nav.dashboard": "Panel", "nav.analytics": "Análisis", "nav.aiAdvisor": "Asesor IA",
        "nav.inventory": "Inventario", "nav.invoices": "Facturas", "nav.recurring": "Recurrente",
        "nav.cashRegister": "Caja", "nav.customers": "Clientes", "nav.settings": "Ajustes",
        "nav.signOut": "Cerrar sesión",
        "auth.login": "Iniciar sesión", "auth.signup": "Registrarse", "auth.email": "Correo electrónico",
        "auth.password": "Contraseña", "auth.forgotPassword": "¿Olvidaste tu contraseña?",
        "auth.signInWithPassword": "Iniciar sesión", "auth.createAccount": "Crear cuenta",
        "auth.noAccount": "¿No tienes cuenta?", "auth.hasAccount": "¿Ya tienes cuenta?",
        "errors.invalidCredentials": "Correo o contraseña incorrectos.",
        "errors.networkError": "Error de conexión.",
        "errors.sessionExpired": "Sesión caducada.",
        "errors.unauthorized": "No autorizado.",
        "errors.serverError": "Error del servidor.",
        "errors.notFound": "Página no encontrada.",
        "success.loggedIn": "¡Bienvenido de nuevo!", "success.loggedOut": "Sesión cerrada.",
    },
    "it": {
        "common.loading": "Caricamento...", "common.error": "Qualcosa è andato storto",
        "common.save": "Salva", "common.cancel": "Annulla", "common.delete": "Elimina",
        "common.edit": "Modifica", "common.create": "Crea", "common.search": "Cerca...",
        "common.noResults": "Nessun risultato", "common.back": "Indietro",
        "nav.dashboard": "Dashboard", "nav.analytics": "Analisi", "nav.aiAdvisor": "Consulente IA",
        "nav.inventory": "Magazzino", "nav.invoices": "Fatture", "nav.recurring": "Ricorrenti",
        "nav.cashRegister": "Cassa", "nav.customers": "Clienti", "nav.settings": "Impostazioni",
        "nav.signOut": "Esci",
        "auth.login": "Accedi", "auth.signup": "Registrati", "auth.email": "Indirizzo email",
        "auth.password": "Password", "auth.forgotPassword": "Password dimenticata?",
        "auth.signInWithPassword": "Accedi", "auth.createAccount": "Crea account",
        "errors.invalidCredentials": "Email o password errati.",
        "errors.sessionExpired": "Sessione scaduta.",
        "errors.notFound": "Pagina non trovata.",
        "success.loggedIn": "Bentornato!", "success.loggedOut": "Sei uscito.",
    },
    "nl": {
        "common.loading": "Laden...", "common.error": "Er ging iets mis",
        "common.save": "Opslaan", "common.cancel": "Annuleren", "common.delete": "Verwijderen",
        "common.edit": "Bewerken", "common.create": "Aanmaken", "common.search": "Zoeken...",
        "common.noResults": "Geen resultaten", "common.back": "Terug",
        "nav.dashboard": "Dashboard", "nav.analytics": "Analyse", "nav.aiAdvisor": "AI-adviseur",
        "nav.inventory": "Voorraad", "nav.invoices": "Facturen", "nav.recurring": "Terugkerend",
        "nav.cashRegister": "Kassa", "nav.customers": "Klanten", "nav.settings": "Instellingen",
        "nav.signOut": "Uitloggen",
        "auth.login": "Inloggen", "auth.signup": "Registreren", "auth.email": "E-mailadres",
        "auth.password": "Wachtwoord", "auth.forgotPassword": "Wachtwoord vergeten?",
        "errors.invalidCredentials": "Onjuist e-mailadres of wachtwoord.",
        "success.loggedIn": "Welkom terug!", "success.loggedOut": "Je bent uitgelogd.",
    },
    "pt": {
        "common.loading": "Carregando...", "common.error": "Algo deu errado",
        "common.save": "Salvar", "common.cancel": "Cancelar", "common.delete": "Excluir",
        "common.edit": "Editar", "common.create": "Criar", "common.search": "Pesquisar...",
        "common.noResults": "Sem resultados", "common.back": "Voltar",
        "nav.dashboard": "Painel", "nav.analytics": "Análise", "nav.aiAdvisor": "Consultor IA",
        "nav.inventory": "Estoque", "nav.invoices": "Faturas", "nav.recurring": "Recorrente",
        "nav.cashRegister": "Caixa", "nav.customers": "Clientes", "nav.settings": "Configurações",
        "nav.signOut": "Sair",
        "auth.login": "Entrar", "auth.signup": "Cadastrar", "auth.email": "E-mail",
        "auth.password": "Senha", "auth.forgotPassword": "Esqueceu a senha?",
        "errors.invalidCredentials": "E-mail ou senha incorretos.",
        "success.loggedIn": "Bem-vindo de volta!", "success.loggedOut": "Você saiu.",
    },

    # ─── Eastern Europe ────────────────────────────────────────────────────
    "pl": {
        "common.loading": "Ładowanie...", "common.error": "Coś poszło nie tak",
        "common.save": "Zapisz", "common.cancel": "Anuluj", "common.delete": "Usuń",
        "common.edit": "Edytuj", "common.create": "Utwórz", "common.search": "Szukaj...",
        "common.noResults": "Brak wyników", "common.back": "Wstecz",
        "nav.dashboard": "Panel", "nav.analytics": "Analityka", "nav.aiAdvisor": "Doradca AI",
        "nav.inventory": "Magazyn", "nav.invoices": "Faktury", "nav.recurring": "Cykliczne",
        "nav.cashRegister": "Kasa", "nav.customers": "Klienci", "nav.settings": "Ustawienia",
        "nav.signOut": "Wyloguj",
        "auth.login": "Zaloguj", "auth.signup": "Zarejestruj", "auth.email": "Adres e-mail",
        "auth.password": "Hasło",
    },
    "cs": {
        "common.loading": "Načítání...", "common.save": "Uložit", "common.cancel": "Zrušit",
        "common.delete": "Smazat", "common.edit": "Upravit", "common.create": "Vytvořit",
        "common.back": "Zpět",
        "nav.dashboard": "Přehled", "nav.inventory": "Sklad", "nav.invoices": "Faktury",
        "nav.customers": "Zákazníci", "nav.settings": "Nastavení", "nav.signOut": "Odhlásit",
        "auth.login": "Přihlásit", "auth.password": "Heslo", "auth.email": "E-mail",
    },
    "sk": {
        "common.loading": "Načítava sa...", "common.save": "Uložiť", "common.cancel": "Zrušiť",
        "common.delete": "Odstrániť", "common.edit": "Upraviť", "common.back": "Späť",
        "nav.dashboard": "Prehľad", "nav.inventory": "Sklad", "nav.invoices": "Faktúry",
        "nav.customers": "Zákazníci", "nav.settings": "Nastavenia", "nav.signOut": "Odhlásiť",
        "auth.login": "Prihlásiť", "auth.password": "Heslo", "auth.email": "E-mail",
    },
    "hu": {
        "common.loading": "Betöltés...", "common.save": "Mentés", "common.cancel": "Mégse",
        "common.delete": "Törlés", "common.edit": "Szerkesztés", "common.back": "Vissza",
        "nav.dashboard": "Áttekintés", "nav.inventory": "Raktár", "nav.invoices": "Számlák",
        "nav.customers": "Ügyfelek", "nav.settings": "Beállítások", "nav.signOut": "Kijelentkezés",
        "auth.login": "Bejelentkezés", "auth.password": "Jelszó", "auth.email": "E-mail",
    },
    "ro": {
        "common.loading": "Se încarcă...", "common.save": "Salvează", "common.cancel": "Anulează",
        "common.delete": "Șterge", "common.edit": "Editează", "common.back": "Înapoi",
        "nav.dashboard": "Tablou de bord", "nav.inventory": "Inventar", "nav.invoices": "Facturi",
        "nav.customers": "Clienți", "nav.settings": "Setări", "nav.signOut": "Deconectare",
        "auth.login": "Autentificare", "auth.password": "Parolă", "auth.email": "E-mail",
    },
    "bg": {
        "common.loading": "Зарежда...", "common.save": "Запази", "common.cancel": "Отказ",
        "common.delete": "Изтрий", "common.back": "Назад",
        "nav.dashboard": "Табло", "nav.inventory": "Склад", "nav.invoices": "Фактури",
        "nav.customers": "Клиенти", "nav.settings": "Настройки", "nav.signOut": "Изход",
        "auth.login": "Вход", "auth.password": "Парола", "auth.email": "Имейл",
    },
    "el": {
        "common.loading": "Φόρτωση...", "common.save": "Αποθήκευση", "common.cancel": "Ακύρωση",
        "common.delete": "Διαγραφή", "common.back": "Πίσω",
        "nav.dashboard": "Πίνακας", "nav.inventory": "Απόθεμα", "nav.invoices": "Τιμολόγια",
        "nav.customers": "Πελάτες", "nav.settings": "Ρυθμίσεις", "nav.signOut": "Αποσύνδεση",
        "auth.login": "Σύνδεση", "auth.password": "Κωδικός", "auth.email": "E-mail",
    },
    "hr": {
        "common.loading": "Učitavanje...", "common.save": "Spremi", "common.cancel": "Odustani",
        "common.delete": "Izbriši", "common.back": "Natrag",
        "nav.dashboard": "Nadzorna ploča", "nav.inventory": "Skladište", "nav.invoices": "Računi",
        "nav.customers": "Klijenti", "nav.settings": "Postavke", "nav.signOut": "Odjava",
        "auth.login": "Prijava", "auth.password": "Lozinka", "auth.email": "E-mail",
    },
    "sl": {
        "common.loading": "Nalaganje...", "common.save": "Shrani", "common.cancel": "Prekliči",
        "common.delete": "Izbriši", "common.back": "Nazaj",
        "nav.dashboard": "Nadzorna plošča", "nav.inventory": "Zaloga", "nav.invoices": "Računi",
        "nav.customers": "Stranke", "nav.settings": "Nastavitve", "nav.signOut": "Odjava",
        "auth.login": "Prijava", "auth.password": "Geslo", "auth.email": "E-pošta",
    },
    "et": {
        "common.loading": "Laadimine...", "common.save": "Salvesta", "common.cancel": "Tühista",
        "common.delete": "Kustuta", "common.back": "Tagasi",
        "nav.dashboard": "Töölaud", "nav.inventory": "Ladu", "nav.invoices": "Arved",
        "nav.customers": "Kliendid", "nav.settings": "Seaded", "nav.signOut": "Logi välja",
        "auth.login": "Logi sisse", "auth.password": "Parool", "auth.email": "E-post",
    },
    "lv": {
        "common.loading": "Ielādē...", "common.save": "Saglabāt", "common.cancel": "Atcelt",
        "common.delete": "Dzēst", "common.back": "Atpakaļ",
        "nav.dashboard": "Panelis", "nav.inventory": "Noliktava", "nav.invoices": "Rēķini",
        "nav.customers": "Klienti", "nav.settings": "Iestatījumi", "nav.signOut": "Iziet",
        "auth.login": "Pieteikties", "auth.password": "Parole", "auth.email": "E-pasts",
    },
    "lt": {
        "common.loading": "Kraunama...", "common.save": "Išsaugoti", "common.cancel": "Atšaukti",
        "common.delete": "Trinti", "common.back": "Atgal",
        "nav.dashboard": "Skydelis", "nav.inventory": "Sandėlis", "nav.invoices": "Sąskaitos",
        "nav.customers": "Klientai", "nav.settings": "Nustatymai", "nav.signOut": "Atsijungti",
        "auth.login": "Prisijungti", "auth.password": "Slaptažodis", "auth.email": "El. paštas",
    },
    "uk": {
        "common.loading": "Завантаження...", "common.save": "Зберегти", "common.cancel": "Скасувати",
        "common.delete": "Видалити", "common.back": "Назад",
        "nav.dashboard": "Панель", "nav.inventory": "Склад", "nav.invoices": "Рахунки",
        "nav.customers": "Клієнти", "nav.settings": "Налаштування", "nav.signOut": "Вийти",
        "auth.login": "Увійти", "auth.password": "Пароль", "auth.email": "Електронна пошта",
    },
    "sr": {
        "common.loading": "Učitavanje...", "common.save": "Sačuvaj", "common.cancel": "Otkaži",
        "common.delete": "Obriši", "common.back": "Nazad",
        "nav.dashboard": "Kontrolna tabla", "nav.inventory": "Zalihe", "nav.invoices": "Fakture",
        "nav.customers": "Klijenti", "nav.settings": "Podešavanja", "nav.signOut": "Odjava",
        "auth.login": "Prijava", "auth.password": "Lozinka", "auth.email": "E-mail",
    },
    "mk": {
        "common.loading": "Се вчитува...", "common.save": "Зачувај", "common.cancel": "Откажи",
        "common.back": "Назад",
        "nav.dashboard": "Панел", "nav.inventory": "Залихи", "nav.invoices": "Фактури",
        "nav.customers": "Клиенти", "nav.settings": "Поставки", "nav.signOut": "Одјави се",
        "auth.login": "Најава", "auth.password": "Лозинка",
    },
    "sq": {
        "common.loading": "Duke u ngarkuar...", "common.save": "Ruaj", "common.cancel": "Anulo",
        "common.delete": "Fshi", "common.back": "Prapa",
        "nav.dashboard": "Paneli", "nav.inventory": "Magazina", "nav.invoices": "Faturat",
        "nav.customers": "Klientët", "nav.settings": "Cilësimet", "nav.signOut": "Dil",
        "auth.login": "Hyr", "auth.password": "Fjalëkalimi", "auth.email": "E-mail",
    },

    # ─── Middle East ───────────────────────────────────────────────────────
    "ar": {
        "common.loading": "جارٍ التحميل...", "common.error": "حدث خطأ ما",
        "common.save": "حفظ", "common.cancel": "إلغاء", "common.delete": "حذف",
        "common.edit": "تعديل", "common.create": "إنشاء", "common.search": "بحث...",
        "common.noResults": "لا توجد نتائج", "common.back": "رجوع",
        "nav.dashboard": "لوحة التحكم", "nav.analytics": "التحليلات", "nav.aiAdvisor": "المستشار الذكي",
        "nav.inventory": "المخزون", "nav.invoices": "الفواتير", "nav.recurring": "متكررة",
        "nav.cashRegister": "الصندوق", "nav.customers": "العملاء", "nav.settings": "الإعدادات",
        "nav.signOut": "تسجيل الخروج",
        "auth.login": "تسجيل الدخول", "auth.signup": "إنشاء حساب", "auth.email": "البريد الإلكتروني",
        "auth.password": "كلمة المرور", "auth.forgotPassword": "نسيت كلمة المرور؟",
        "errors.invalidCredentials": "البريد الإلكتروني أو كلمة المرور غير صحيحة.",
        "errors.sessionExpired": "انتهت الجلسة.",
        "errors.notFound": "الصفحة غير موجودة.",
        "success.loggedIn": "مرحبًا بعودتك!", "success.loggedOut": "تم تسجيل الخروج.",
    },
    "he": {
        "common.loading": "טוען...", "common.error": "משהו השתבש",
        "common.save": "שמור", "common.cancel": "ביטול", "common.delete": "מחק",
        "common.edit": "ערוך", "common.create": "צור", "common.search": "חיפוש...",
        "common.noResults": "אין תוצאות", "common.back": "חזרה",
        "nav.dashboard": "לוח בקרה", "nav.analytics": "ניתוח", "nav.aiAdvisor": "יועץ AI",
        "nav.inventory": "מלאי", "nav.invoices": "חשבוניות", "nav.recurring": "חוזר",
        "nav.cashRegister": "קופה", "nav.customers": "לקוחות", "nav.settings": "הגדרות",
        "nav.signOut": "התנתק",
        "auth.login": "התחבר", "auth.signup": "הרשמה", "auth.email": "כתובת אימייל",
        "auth.password": "סיסמה", "auth.forgotPassword": "שכחת סיסמה?",
        "errors.invalidCredentials": "אימייל או סיסמה שגויים.",
        "success.loggedIn": "ברוך שובך!", "success.loggedOut": "התנתקת.",
    },
    "tr": {
        "common.loading": "Yükleniyor...", "common.error": "Bir hata oluştu",
        "common.save": "Kaydet", "common.cancel": "İptal", "common.delete": "Sil",
        "common.edit": "Düzenle", "common.create": "Oluştur", "common.search": "Ara...",
        "common.noResults": "Sonuç yok", "common.back": "Geri",
        "nav.dashboard": "Kontrol Paneli", "nav.analytics": "Analiz", "nav.aiAdvisor": "AI Danışmanı",
        "nav.inventory": "Envanter", "nav.invoices": "Faturalar", "nav.recurring": "Yinelenen",
        "nav.cashRegister": "Kasa", "nav.customers": "Müşteriler", "nav.settings": "Ayarlar",
        "nav.signOut": "Çıkış yap",
        "auth.login": "Giriş yap", "auth.signup": "Kayıt ol", "auth.email": "E-posta",
        "auth.password": "Şifre", "auth.forgotPassword": "Şifrenizi mi unuttunuz?",
        "errors.invalidCredentials": "E-posta veya şifre hatalı.",
        "success.loggedIn": "Tekrar hoş geldiniz!", "success.loggedOut": "Çıkış yapıldı.",
    },
}

# Locales that are RTL — used by downstream UI to set <html dir="rtl">.
RTL_LOCALES = {"ar", "he"}


def set_path(d: dict[str, Any], dotted: str, value: str) -> None:
    keys = dotted.split(".")
    cur = d
    for k in keys[:-1]:
        if not isinstance(cur.get(k), dict):
            cur[k] = {}
        cur = cur[k]
    cur[keys[-1]] = value


def main() -> None:
    en_path = MSGS / "en.json"
    if not en_path.exists():
        raise SystemExit("frontend/messages/en.json missing")
    en_data = json.loads(en_path.read_text(encoding="utf-8"))

    changed = 0
    for locale, translations in T.items():
        path = MSGS / f"{locale}.json"
        if not path.exists():
            # Seed from English first
            path.write_text(json.dumps(en_data, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
        data = json.loads(path.read_text(encoding="utf-8"))
        for dotted, value in translations.items():
            set_path(data, dotted, value)
        # Mark direction for RTL handling
        data["_meta"] = {"locale": locale, "dir": "rtl" if locale in RTL_LOCALES else "ltr"}
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        changed += 1

    print(f"Translated core strings for {changed} locales "
          f"(RTL: {', '.join(sorted(RTL_LOCALES))}).")
    # Summary of coverage — how many core keys per locale
    for locale, translations in sorted(T.items()):
        print(f"  {locale:4s}  {len(translations):3d} core strings")


if __name__ == "__main__":
    main()
