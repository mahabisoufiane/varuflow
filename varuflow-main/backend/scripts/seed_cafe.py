#!/usr/bin/env python3
"""Nordisk Kaffehandel & Delikatess AB — Swedish market demo seed.

Creates a fully-populated demo organisation for a Stockholm-based specialty
coffee and gourmet food wholesale company that supplies Swedish cafés, hotels,
bakeries, and restaurants.

Every screen in the app will look live:
  Dashboard   – growing revenue curve, KPI tiles, low-stock alerts
  Inventory   – 38 products with real images, varied stock levels
  Invoices    – 70+ invoices over 6 months (PAID/SENT/OVERDUE/DRAFT)
  POS         – 3 recent in-store cash-register sessions
  Analytics   – month-over-month growth, best-seller ranking
  Customers   – 12 named Swedish B2B accounts

Usage (from backend/):
    python scripts/seed_cafe.py

Login:    demo@varuflow.se
Password: Demo1234!
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from random import Random

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# ── Config ─────────────────────────────────────────────────────────────────────

SUPABASE_URL      = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
)
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

DEMO_EMAIL    = "demo@varuflow.se"
DEMO_PASSWORD = "Demo1234!"
DEMO_ORG_NAME = "Nordisk Kaffehandel & Delikatess AB"
DEMO_ORG_NO   = "556889-2347"
DEMO_VAT      = "SE556889234701"
DEMO_ADDRESS  = "Kungsgatan 22, 111 43 Stockholm"

rng = Random(99)   # deterministic — same data every run

_U = "https://images.unsplash.com/photo-"  # Unsplash CDN prefix
_Q = "?w=600&q=82&auto=format&fit=crop"    # Unsplash query string
_P = "https://picsum.photos/seed/"          # Picsum reliable fallback

def _u(photo_id: str) -> str:
    return f"{_U}{photo_id}{_Q}"

def _p(seed: str) -> str:
    return f"{_P}{seed}/600/600"

# ── Product catalogue ──────────────────────────────────────────────────────────
# Prices in SEK. tax=12 for food/beverage (mat/dryck), 25 for equipment/packaging.
# stock intentionally varied: some healthy, some low (below min_stock).

PRODUCTS = [
    # ── Kaffe & Espresso ───────────────────────────────────────────────────────
    {
        "name": 'Espresso Blend "Stockholmsrost" 1 kg',
        "sku": "COFFEE-ESP-STH-1KG",
        "category": "Kaffe & Te",
        "sell": 189, "cost": 85, "tax": 12, "unit": "kg",
        "min_stock": 30, "stock": 142,
        "barcode": "7310075022023",
        "description": (
            "Mörk, fyllig espressoblandning med toner av mörk choklad och "
            "rostade hasselnötter. Perfekt till cappuccino och flat white. "
            "Rost: mörk. Ursprung: Brasilien/Colombia blend."
        ),
        "image_url": _u("1495474472287-4d71bcdd2085"),
    },
    {
        "name": "Filterkaffé Mellanrost 500 g",
        "sku": "COFFEE-FILTER-MR-500",
        "category": "Kaffe & Te",
        "sell": 79, "cost": 34, "tax": 12, "unit": "fp",
        "min_stock": 40, "stock": 298,
        "barcode": "7310075001028",
        "description": (
            "Välbalanserat mellanrostat filterkaffé med mjuk smak och "
            "lång eftersmak av karamell. Passar alla kaffebryggare. "
            "Mald för droppbryggare. UTZ-certifierat."
        ),
        "image_url": _u("1442512595331-8f22b2e9af77"),
    },
    {
        "name": "Kaffebönor Kenya AA 250 g",
        "sku": "COFFEE-KE-AA-250",
        "category": "Kaffe & Te",
        "sell": 145, "cost": 66, "tax": 12, "unit": "fp",
        "min_stock": 20, "stock": 87,
        "barcode": "7394567000113",
        "description": (
            "Kenyanaskt single origin med ljus syra, toner av svartvinbär "
            "och citrus. Light roast. Odlat vid 1 800 m höjd i Nyeri-regionen. "
            "Specialty grade 87 p SCA."
        ),
        "image_url": _u("1509042239860-f550ce710b93"),
    },
    {
        "name": "Kaffebönor Ethiopia Yirgacheffe 250 g",
        "sku": "COFFEE-ET-YIR-250",
        "category": "Kaffe & Te",
        "sell": 165, "cost": 76, "tax": 12, "unit": "fp",
        "min_stock": 15, "stock": 54,
        "barcode": "7394567000120",
        "description": (
            "Naturprocessad Ethiopia Yirgacheffe med blommiga och fruktiga "
            "toner. Blåbär, jasmin och exotisk frukt. SCA 88 p. "
            "Wash process. Heirloom-varieteter."
        ),
        "image_url": _u("1511920170033-f8396924c348"),
    },
    {
        "name": "Kaffebönor Colombia Huila 500 g",
        "sku": "COFFEE-CO-HUI-500",
        "category": "Kaffe & Te",
        "sell": 149, "cost": 68, "tax": 12, "unit": "fp",
        "min_stock": 20, "stock": 11,   # ← LOW STOCK
        "barcode": "7394567000144",
        "description": (
            "Medium roast från Colombia Huila med kakaotoner, "
            "panela och röda äpplen. Washed process, odlat av "
            "småbönder i Acevedo. Fairtrade och ekologiskt."
        ),
        "image_url": _u("1459452567049-4c258a6e1b09"),
    },
    {
        "name": "Oatly Barista Edition 1 L",
        "sku": "DAIRY-OATLY-BAR-1L",
        "category": "Kaffe & Te",
        "sell": 28, "cost": 13, "tax": 12, "unit": "st",
        "min_stock": 80, "stock": 432,
        "barcode": "7394376616010",
        "description": (
            "Havredryck speciellt framtagen för barister — skummar perfekt "
            "och ger en krämig textur i latte och cappuccino. "
            "Laktosfri, vegansk. Tillverkad i Sverige."
        ),
        "image_url": _p("oatly-barista"),
    },
    {
        "name": "Earl Grey Premium 100 påsar",
        "sku": "TEA-EARLS-100P",
        "category": "Kaffe & Te",
        "sell": 139, "cost": 62, "tax": 12, "unit": "fp",
        "min_stock": 25, "stock": 96,
        "barcode": "5000156006062",
        "description": (
            "Klassisk Earl Grey med bergamot-arom från bergapressad citrusolja. "
            "Pyramidpåsar med Darjeeling och Ceylon blend. "
            "Rainforest Alliance-certifierat."
        ),
        "image_url": _u("1556679343-c7306c1976bc"),
    },
    {
        "name": "English Breakfast Löste 1 kg",
        "sku": "TEA-ENGB-LOOSE-1KG",
        "category": "Kaffe & Te",
        "sell": 389, "cost": 178, "tax": 12, "unit": "kg",
        "min_stock": 10, "stock": 38,
        "barcode": "5000156140117",
        "description": (
            "Robust Assam/Ceylon-blend med fyllig smak och robust kropp. "
            "Passar perfekt med mjölk. Storbulk för hög omsättning. "
            "Förpackad i lufttät ziplock-påse."
        ),
        "image_url": _p("english-breakfast-tea"),
    },
    {
        "name": "Matchate Ceremonial Grade 100 g",
        "sku": "TEA-MATCHA-CER-100",
        "category": "Kaffe & Te",
        "sell": 579, "cost": 268, "tax": 12, "unit": "fp",
        "min_stock": 8, "stock": 6,    # ← LOW STOCK
        "barcode": "4528483013882",
        "description": (
            "Japansk ceremonial grade matcha från Uji, Kyoto. "
            "Intensivt grön färg, len och söt smak utan bitterhet. "
            "Perfekt för matcha latte och traditionell whisk-beredning."
        ),
        "image_url": _p("matcha-ceremonial"),
    },
    {
        "name": "Chai Latte Pulver 1 kg",
        "sku": "TEA-CHAI-PULVER-1KG",
        "category": "Kaffe & Te",
        "sell": 245, "cost": 112, "tax": 12, "unit": "kg",
        "min_stock": 15, "stock": 63,
        "barcode": "8720246027128",
        "description": (
            "Aromatisk chai-latte-mix med kanel, ingefära, kardemumma och "
            "svartpeppar. Blandas med varm mjölk eller havremjölk. "
            "Koffeinfri. Vegan. 1:4 utspädningsförhållande."
        ),
        "image_url": _p("chai-latte"),
    },

    # ── Maskiner & Utrustning ──────────────────────────────────────────────────
    {
        "name": "Espressomaskin Jura E8 Helautomatisk",
        "sku": "MACH-JURA-E8",
        "category": "Maskiner & Utrustning",
        "sell": 12990, "cost": 6500, "tax": 25, "unit": "st",
        "min_stock": 3, "stock": 7,
        "barcode": "7640174698600",
        "description": (
            "Helautomatisk espressomaskin med 15-bars pumptryck och inbyggd "
            "mjölkskummare. Kapacitet: 25 koppar/dag. Inkl. 2 års garanti. "
            "Passar café, hotell och konferensrum."
        ),
        "image_url": _u("1585737360483-34b1ba6b94d0"),
    },
    {
        "name": "Kaffekvarn Mazzer Mini E Type B",
        "sku": "MACH-MAZZER-MINI-E",
        "category": "Maskiner & Utrustning",
        "sell": 5490, "cost": 3200, "tax": 25, "unit": "st",
        "min_stock": 2, "stock": 5,
        "barcode": "8026446101157",
        "description": (
            "Professionell espressokvarn med 58mm flat stålskivor. "
            "Dosering på begäran via timer. Tillverkad i Italien. "
            "Kapacitet 3–4 kg/dag. Passar de flesta kaffebarer."
        ),
        "image_url": _p("coffee-grinder-mazzer"),
    },
    {
        "name": "Kaffebryggare Moccamaster KBG 741",
        "sku": "MACH-MOCCAMASTER-KBG741",
        "category": "Maskiner & Utrustning",
        "sell": 1890, "cost": 1050, "tax": 25, "unit": "st",
        "min_stock": 5, "stock": 19,
        "barcode": "8712072400337",
        "description": (
            "Ikonisk holländsk kaffebryggare med 1,25L glaskaraff. "
            "Brygger 10 koppar på 6 minuter vid optimal temperatur 92–96 °C. "
            "Tillverkad i Holland. ECBC-certifierad. 5 års garanti."
        ),
        "image_url": _u("1506619087450-d2a12be36909"),
    },
    {
        "name": "Mjölkskummare Jura HP2",
        "sku": "MACH-JURA-HP2",
        "category": "Maskiner & Utrustning",
        "sell": 1090, "cost": 590, "tax": 25, "unit": "st",
        "min_stock": 4, "stock": 9,
        "barcode": "7640174693353",
        "description": (
            "Automatisk mjölkskummare för professionellt mikrofiberskum. "
            "Passar kallt- och varmskum. Kapacitet 400 ml. Diskmaskinssäkert glas. "
            "Lämplig för latte art."
        ),
        "image_url": _u("1497935586351-b67a49e012bf"),
    },
    {
        "name": "Kaffevåg Acaia Pearl 2 kg",
        "sku": "MACH-ACAIA-PEARL",
        "category": "Maskiner & Utrustning",
        "sell": 2190, "cost": 1295, "tax": 25, "unit": "st",
        "min_stock": 3, "stock": 8,
        "barcode": "4718688000000",
        "description": (
            "Precisionsvåg för espresso och pour-over med Bluetooth och app. "
            "Noggrannhet ±0,1 g. Max 2 kg. USB-C laddning. "
            "Vattentålig yta i rostfritt stål."
        ),
        "image_url": _p("acaia-pearl-scale"),
    },
    {
        "name": "AeroPress Go Resepaket",
        "sku": "MACH-AEROPRESS-GO",
        "category": "Maskiner & Utrustning",
        "sell": 690, "cost": 340, "tax": 25, "unit": "st",
        "min_stock": 10, "stock": 34,
        "barcode": "0802591014543",
        "description": (
            "Kompakt resebryggsystem med mugg som fungerar som förvaringsväska. "
            "Inkl. 350 filter. Brygger 1 kopp på 60 sekunder. "
            "BPA-fritt. Perfekt kafégåva eller take-home kit."
        ),
        "image_url": _p("aeropress-go"),
    },
    {
        "name": "Hario V60 Startkit Keramik",
        "sku": "MACH-HARIO-V60-KIT",
        "category": "Maskiner & Utrustning",
        "sell": 490, "cost": 228, "tax": 25, "unit": "st",
        "min_stock": 8, "stock": 26,
        "barcode": "4977642721593",
        "description": (
            "Japanskt pour-over-set i vit keramik. Inkl. V60 droppare, "
            "200 pappersfilter och gooseneck-kanna 600 ml. "
            "Ideal för specialty coffee-upplevelse hemma och på kafé."
        ),
        "image_url": _p("hario-v60-pourover"),
    },

    # ── Bakverk & Råvaror ──────────────────────────────────────────────────────
    {
        "name": "Vetemjöl Tipo 00 Extra 25 kg",
        "sku": "BAKE-FLOUR-T00-25KG",
        "category": "Bakverk & Råvaror",
        "sell": 285, "cost": 130, "tax": 12, "unit": "säck",
        "min_stock": 10, "stock": 44,
        "barcode": "8001250000002",
        "description": (
            "Fint vetemjöl av typ 00 från italienska Molino Grassi. "
            "Proteininnehåll 12 %. Idealiskt för croissanter, pizza och "
            "fint bakverk. Glutennätverk ger luftig struktur."
        ),
        "image_url": _u("1461368100804-9abd9ad9e10d"),
    },
    {
        "name": "Smör Normalsaltat Arla 1 kg",
        "sku": "BAKE-BUTTER-ARLA-1KG",
        "category": "Bakverk & Råvaror",
        "sell": 155, "cost": 79, "tax": 12, "unit": "fp",
        "min_stock": 20, "stock": 88,
        "barcode": "7310340114020",
        "description": (
            "Ekologiskt normalsaltat smör från Arla. 82 % fetthalt. "
            "Fryst transport. Idealiskt för bakelse, smördeg och "
            "rulltårta. Hög prestanda vid värmebehandling."
        ),
        "image_url": _p("butter-arla"),
    },
    {
        "name": "Mandelmassa Aros 1 kg",
        "sku": "BAKE-MARZIPAN-1KG",
        "category": "Bakverk & Råvaror",
        "sell": 229, "cost": 106, "tax": 12, "unit": "fp",
        "min_stock": 12, "stock": 47,
        "barcode": "7317580000000",
        "description": (
            "Klassisk svensk mandelmassa med 25 % äkta mandel. "
            "Perfekt till semla, prinsesstårtorna och marsipanskivor. "
            "Söt, len konsistens. Glutenfri. Tillverkad i Västerås."
        ),
        "image_url": _p("marzipan-mandelmassa"),
    },
    {
        "name": "Valrhona Caraïbe 66 % Mörk Choklad 3 kg",
        "sku": "BAKE-CHOC-VALR-3KG",
        "category": "Bakverk & Råvaror",
        "sell": 890, "cost": 492, "tax": 12, "unit": "fp",
        "min_stock": 8, "stock": 4,    # ← LOW STOCK
        "barcode": "3046920009994",
        "description": (
            "Premium mörk couverture-choklad från Valrhona, Frankrike. "
            "Smakprofil: fyllig kakao, torkad frukt, rostat kaffe. "
            "Couverture-kvalitet för ganacher, tryffel och glasyr."
        ),
        "image_url": _u("1481290239668-b9ecb7c24f0a"),
    },
    {
        "name": "Florsocker Hushållsbruk 1 kg",
        "sku": "BAKE-ICING-SUGAR-1KG",
        "category": "Bakverk & Råvaror",
        "sell": 39, "cost": 16, "tax": 12, "unit": "fp",
        "min_stock": 30, "stock": 178,
        "barcode": "7310640012345",
        "description": (
            "Fint florsocker utan klumpbildning, idealiskt för glasyr, "
            "macarons och pudersocker-dekoration. Förpackad i tät påse "
            "med ziplock-förslutning."
        ),
        "image_url": _p("powdered-sugar"),
    },
    {
        "name": "Vaniljstänger Bourbon Tahiti 10 g",
        "sku": "BAKE-VANILLA-10G",
        "category": "Bakverk & Råvaror",
        "sell": 95, "cost": 44, "tax": 12, "unit": "fp",
        "min_stock": 20, "stock": 82,
        "barcode": "3275940012009",
        "description": (
            "Ekologiska Bourbon-vaniljstänger från Tahiti. "
            "Intensiv, blommig och krämig vaniljarom. "
            "2 stänger per förpackning. Idealisk för crème brûlée, "
            "vaniljsås och bakverk."
        ),
        "image_url": _p("vanilla-beans"),
    },
    {
        "name": "Frigolitägg L 30-pack Rumstempererade",
        "sku": "BAKE-EGGS-L-30PK",
        "category": "Bakverk & Råvaror",
        "sell": 169, "cost": 84, "tax": 12, "unit": "fp",
        "min_stock": 15, "stock": 56,
        "barcode": "7312345600023",
        "description": (
            "Frigolitägg storlek L, 30 per förpackning. Ekologisk hållning, "
            "frigående höns. Idealisk för cakery med hög produktion. "
            "Levereras i styroporbox med kylkedja."
        ),
        "image_url": _p("eggs-30pack"),
    },
    {
        "name": "Hasselnötsmassa Piemonte 1 kg",
        "sku": "BAKE-HAZELNUT-1KG",
        "category": "Bakverk & Råvaror",
        "sell": 345, "cost": 162, "tax": 12, "unit": "fp",
        "min_stock": 8, "stock": 29,
        "barcode": "8000300009997",
        "description": (
            "100 % ren hasselnötsmassa från Piemonte-regionen. "
            "Rostad och mald till slät konsistens utan tillsatser. "
            "Perfekt för pralin, gianduja och nötbaserade ganacher."
        ),
        "image_url": _p("hazelnut-paste"),
    },

    # ── Förpackning & Engångsmaterial ──────────────────────────────────────────
    {
        "name": "Pappmuggar Kraft 12 oz 50-pack",
        "sku": "PACK-CUP-KRAFT-12OZ-50",
        "category": "Förpackning & Engångs",
        "sell": 149, "cost": 72, "tax": 25, "unit": "förp",
        "min_stock": 50, "stock": 312,
        "barcode": "7394001100123",
        "description": (
            "Enkelskiktad pappmuggar i kraftpapper med PE-beläggning. "
            "12 oz / 350 ml. Tryckt med neutralt kafémönster. "
            "Passar alla gängse 12 oz-lock. FSC-certifierat papper."
        ),
        "image_url": _u("1568702846914-96b305d2aaeb"),
    },
    {
        "name": "Lock till 12 oz Pappmuggar 50-pack",
        "sku": "PACK-LID-12OZ-50",
        "category": "Förpackning & Engångs",
        "sell": 79, "cost": 38, "tax": 25, "unit": "förp",
        "min_stock": 50, "stock": 285,
        "barcode": "7394001100130",
        "description": (
            "Dome-lock i plast för 12 oz/350 ml pappmuggar. "
            "Sipple-hål med flip-stängning. Passar standardmuggar 80 mm. "
            "PP-plast, BPA-fritt."
        ),
        "image_url": _p("coffee-cup-lid"),
    },
    {
        "name": "Pappmuggar 8 oz 50-pack",
        "sku": "PACK-CUP-KRAFT-8OZ-50",
        "category": "Förpackning & Engångs",
        "sell": 129, "cost": 60, "tax": 25, "unit": "förp",
        "min_stock": 40, "stock": 198,
        "barcode": "7394001100147",
        "description": (
            "Pappersmugg 8 oz/240 ml för espresso och americano. "
            "Dubbelskiktat för bättre värmeisolering. "
            "FSC-certifierat. Passar 80 mm lock."
        ),
        "image_url": _p("small-coffee-cups"),
    },
    {
        "name": "Papperskassar Kraft Medium 100-pack",
        "sku": "PACK-BAG-KRAFT-M-100",
        "category": "Förpackning & Engångs",
        "sell": 89, "cost": 44, "tax": 25, "unit": "förp",
        "min_stock": 30, "stock": 142,
        "barcode": "7394001200456",
        "description": (
            "Bruna kraftpapperskassar med vridna handtag. "
            "Mått: 18×8×22 cm. 100 per förpackning. "
            "FSC-certifierat. Idealisk för takeaway och gifting."
        ),
        "image_url": _u("1558618666-fcd25c85cd64"),
    },
    {
        "name": "Bakpåsar Cellofan 18×30 cm 100-pack",
        "sku": "PACK-CELLOPHANE-100",
        "category": "Förpackning & Engångs",
        "sell": 109, "cost": 52, "tax": 25, "unit": "förp",
        "min_stock": 25, "stock": 96,
        "barcode": "7394001300789",
        "description": (
            "Transparenta cellofanpåsar för bullar, kakor och kanelknutar. "
            "18×30 cm. Förseglbara med flatblock. "
            "Livsmedelsgodkänt material. 100-pack."
        ),
        "image_url": _p("bakery-cellophane-bags"),
    },
    {
        "name": "Servetter 24×24 cm 1-lags 500-pack",
        "sku": "PACK-NAPKIN-24-500",
        "category": "Förpackning & Engångs",
        "sell": 79, "cost": 36, "tax": 25, "unit": "förp",
        "min_stock": 40, "stock": 220,
        "barcode": "7394001400012",
        "description": (
            "Vita enlagsservetter 24×24 cm. Mjuka och absorberande. "
            "500 per förpackning. FSC-certifierat papper. "
            "Lämpliga för bord och take-away."
        ),
        "image_url": _p("white-napkins"),
    },
    {
        "name": "Tårtaskar Medium 22×22×10 cm 25-pack",
        "sku": "PACK-CAKEBOX-M-25",
        "category": "Förpackning & Engångs",
        "sell": 125, "cost": 60, "tax": 25, "unit": "förp",
        "min_stock": 20, "stock": 12,   # ← LOW STOCK
        "barcode": "7394001500345",
        "description": (
            "Vita tårtaskar med fönsterlucka i vit kartong. "
            "Mått: 22×22×10 cm. Monteras enkelt. "
            "Passar prinsesstårta, mazarintårta och cheesecake."
        ),
        "image_url": _p("cake-box"),
    },

    # ── Dryck & Syroper ────────────────────────────────────────────────────────
    {
        "name": "San Pellegrino Naturell 33 cl (24-pack)",
        "sku": "DRINK-SAPE-33-24PK",
        "category": "Dryck & Syroper",
        "sell": 169, "cost": 79, "tax": 12, "unit": "förp",
        "min_stock": 20, "stock": 84,
        "barcode": "8002270000022",
        "description": (
            "Naturligt mineralvatten med fin pärla. "
            "Källa: San Pellegrino Terme, Bergamo, Italien. "
            "Lämplig som bordssoda och till espresso. "
            "24 x 33 cl glasflaskor."
        ),
        "image_url": _u("1559827291-72ebba977e3f"),
    },
    {
        "name": "Apelsinjuice Ekologisk 1 L (12-pack)",
        "sku": "DRINK-OJ-EKO-1L-12",
        "category": "Dryck & Syroper",
        "sell": 189, "cost": 90, "tax": 12, "unit": "förp",
        "min_stock": 15, "stock": 62,
        "barcode": "4056489000001",
        "description": (
            "Ekologisk pressad apelsinjuice utan tillsatser. "
            "1 liters Tetra-förpackning. 12 per kartong. "
            "Producerad i Spanien av ekologiska apelsiner. "
            "Inte från koncentrat."
        ),
        "image_url": _u("1560508038-bb52f96327e3"),
    },
    {
        "name": "Kombucha Original 330 ml (12-pack)",
        "sku": "DRINK-KOMBUCHA-330-12",
        "category": "Dryck & Syroper",
        "sell": 279, "cost": 138, "tax": 12, "unit": "förp",
        "min_stock": 12, "stock": 5,    # ← LOW STOCK
        "barcode": "7394888100001",
        "description": (
            "Swedish Brewed Kombucha med levande kulturer. "
            "Original-smak: syrlig och lätt söt. "
            "Raw, ekologisk, ej pastöriserad. "
            "330 ml glasflaska. 12 per kartong."
        ),
        "image_url": _p("kombucha-bottle"),
    },
    {
        "name": "Monin Vanilj Sirap 1 L",
        "sku": "DRINK-MONIN-VAN-1L",
        "category": "Dryck & Syroper",
        "sell": 189, "cost": 92, "tax": 12, "unit": "fl",
        "min_stock": 15, "stock": 72,
        "barcode": "3052910023012",
        "description": (
            "Fransk premiumsirap med äkta Bourbon-vaniljarom. "
            "Sockerbas för latte, smoothies och cocktails. "
            "Glutenfri, vegansk. Doserpump ingår ej — säljs separat."
        ),
        "image_url": _p("monin-vanilla-syrup"),
    },
    {
        "name": "Monin Karamell Sirap 1 L",
        "sku": "DRINK-MONIN-CAR-1L",
        "category": "Dryck & Syroper",
        "sell": 189, "cost": 92, "tax": 12, "unit": "fl",
        "min_stock": 15, "stock": 58,
        "barcode": "3052910018087",
        "description": (
            "Rik karamellsirap med smör-karamell-arom. "
            "Passar caramel macchiato, frappé och kold-brygg. "
            "Utan artificiella färgämnen. 1 L glasflaska."
        ),
        "image_url": _p("monin-caramel-syrup"),
    },
    {
        "name": "Monin Hasselnöt Sirap 1 L",
        "sku": "DRINK-MONIN-HAZ-1L",
        "category": "Dryck & Syroper",
        "sell": 189, "cost": 92, "tax": 12, "unit": "fl",
        "min_stock": 15, "stock": 44,
        "barcode": "3052910019039",
        "description": (
            "Nötig hasselnötsirap med rostade nöttoner. "
            "Klassisk kafékombination: hazelnut latte och café mocha. "
            "Vegansk. Sockerbas. 1 L glasflaska med korklock."
        ),
        "image_url": _p("monin-hazelnut-syrup"),
    },
    {
        "name": "Monin Doserpump för 1 L-flaska",
        "sku": "DRINK-MONIN-PUMP-1L",
        "category": "Dryck & Syroper",
        "sell": 79, "cost": 38, "tax": 25, "unit": "st",
        "min_stock": 20, "stock": 95,
        "barcode": "3052910090013",
        "description": (
            "Plast-doserpump för Monin 1 L-flaskor. "
            "Ger 1 cl sirap per pumpning. Lätt att installera och rengöra. "
            "Passar alla Monin 1 L-flaskor med standardmunstycke."
        ),
        "image_url": _p("syrup-pump"),
    },

    # ── Choklad & Konfektyr ────────────────────────────────────────────────────
    {
        "name": "Valrhona Ivoire Vit Choklad 3 kg",
        "sku": "CHOC-VALR-IVO-3KG",
        "category": "Choklad & Konfektyr",
        "sell": 790, "cost": 432, "tax": 12, "unit": "fp",
        "min_stock": 8, "stock": 31,
        "barcode": "3046920029954",
        "description": (
            "Premiumvit couverture med rik smörkaramell-profil. "
            "35 % kakaomör, lämplig för mousser, pannacotta och tryffelglasskivor. "
            "Callets-format för enkel smältning."
        ),
        "image_url": _p("white-chocolate"),
    },
    {
        "name": "Callebaut Ruby RB1 Choklad 2,5 kg",
        "sku": "CHOC-CALLA-RUBY-2KG",
        "category": "Choklad & Konfektyr",
        "sell": 950, "cost": 524, "tax": 12, "unit": "fp",
        "min_stock": 6, "stock": 18,
        "barcode": "5410522003452",
        "description": (
            "Naturligt rosa ruby-choklad med bärsyra utan tillsatt färg eller arom. "
            "Unik fruktig profil — hallon, tranbär. "
            "2,5 kg callets. Tempereras på samma vis som mjölkchoklad."
        ),
        "image_url": _p("ruby-chocolate"),
    },
    {
        "name": "Guanaja 70 % Mörk Couverture 3 kg",
        "sku": "CHOC-VALR-GUA-3KG",
        "category": "Choklad & Konfektyr",
        "sell": 890, "cost": 490, "tax": 12, "unit": "fp",
        "min_stock": 8, "stock": 7,    # LOW
        "barcode": "3046920021026",
        "description": (
            "Valrhona Guanaja — intensiv 70 % mörk choklad med bitter kakao "
            "och toner av rostad kaffe. Ikonisk couverture sedan 1986. "
            "Callets-format. Uppföljare till Pur Caraïbe."
        ),
        "image_url": _u("1481290239668-b9ecb7c24f0a"),
    },
    {
        "name": "Kakaopulver Dutched 1 kg",
        "sku": "CHOC-COCOA-DUT-1KG",
        "category": "Choklad & Konfektyr",
        "sell": 145, "cost": 68, "tax": 12, "unit": "fp",
        "min_stock": 20, "stock": 93,
        "barcode": "8000300500016",
        "description": (
            "Alkaliserat (dutched) kakaopulver med djup mahognyfärg och "
            "mild smak. Fetthalt 10–12 %. Perfekt för brownies, "
            "chokladkakor och kakaobaserade drycker."
        ),
        "image_url": _p("cocoa-powder"),
    },
    {
        "name": "Kakaonibs Raw Ekologisk 500 g",
        "sku": "CHOC-NIBS-RAW-500",
        "category": "Choklad & Konfektyr",
        "sell": 195, "cost": 90, "tax": 12, "unit": "fp",
        "min_stock": 12, "stock": 64,
        "barcode": "8719324000086",
        "description": (
            "Krossade råkakaoböner utan socker. Intensiv kakaobitterhet. "
            "Ekologisk odling, Peru. Passar granola, muffins och chokladpralin. "
            "500 g ziplock-förpackning."
        ),
        "image_url": _p("cacao-nibs"),
    },
    {
        "name": "Strössel Pärlemor Regnbåge 250 g",
        "sku": "DECO-SPRINKLE-250",
        "category": "Choklad & Konfektyr",
        "sell": 89, "cost": 38, "tax": 12, "unit": "fp",
        "min_stock": 20, "stock": 145,
        "barcode": "7394001600088",
        "description": (
            "Blandat pärlemorsströssel i regnbågsfärger. "
            "Nonpareils, stars och hearts. Lämpligt för tårtor, "
            "cupcakes och glass. Glutenfri."
        ),
        "image_url": _p("rainbow-sprinkles"),
    },

    # ── Importerade Delikatesser ────────────────────────────────────────────────
    {
        "name": "Parmesan Reggiano DOP 24 mån 1 kg",
        "sku": "DELI-PARM-DOP-1KG",
        "category": "Importerade Delikatesser",
        "sell": 689, "cost": 398, "tax": 12, "unit": "kg",
        "min_stock": 5, "stock": 22,
        "barcode": "8001350024001",
        "description": (
            "Äkta Parmigiano-Reggiano DOP, lagrad 24 månader. "
            "Importerad direkt från Emilia-Romagna. "
            "Fruktiga, nötiga toner med lång eftersmak. "
            "Levereras vakuumförpackad i 1 kg bit."
        ),
        "image_url": _p("parmesan-cheese"),
    },
    {
        "name": "Olivolja Extra Virgin Kreta 5 L",
        "sku": "DELI-OLIVE-CRETE-5L",
        "category": "Importerade Delikatesser",
        "sell": 495, "cost": 248, "tax": 12, "unit": "kan",
        "min_stock": 8, "stock": 34,
        "barcode": "5204031000025",
        "description": (
            "Kallpressad extra virgin olivolja från Kreta, Koroneiki-druvor. "
            "Syrahalt < 0,4 %. Gräsig, pepprigt eftersmak. "
            "5 L plåtburk. Bäst-före 18 månader. EU-certifierat ursprung."
        ),
        "image_url": _p("olive-oil-tin"),
    },
    {
        "name": "Balsamico Condimento 3 år 500 ml",
        "sku": "DELI-BALSA-3Y-500",
        "category": "Importerade Delikatesser",
        "sell": 395, "cost": 178, "tax": 12, "unit": "fl",
        "min_stock": 6, "stock": 28,
        "barcode": "8003170000006",
        "description": (
            "Traditionell balsamvinäger från Modena, lagrad 3 år i ekfat. "
            "Sötsyrlig och komplex. Perfekt som glasyr, "
            "dressing eller på parmesanbit. 500 ml glasflaska."
        ),
        "image_url": _p("balsamic-vinegar"),
    },
    {
        "name": "Tryffelolja Vit Alba 250 ml",
        "sku": "DELI-TRUFFLE-W-250",
        "category": "Importerade Delikatesser",
        "sell": 395, "cost": 185, "tax": 12, "unit": "fl",
        "min_stock": 5, "stock": 19,
        "barcode": "8003490100111",
        "description": (
            "Italiensk tryffelolja baserad på extra virgin olivolja och "
            "vit tryffel-arom. Intensiv, jordnära doft. "
            "Används sparsmakat på risotto, pasta och ägg. 250 ml."
        ),
        "image_url": _p("truffle-oil"),
    },
    {
        "name": "Mozzarella di Bufala Campana 500 g",
        "sku": "DELI-MOZZ-BUF-500",
        "category": "Importerade Delikatesser",
        "sell": 189, "cost": 99, "tax": 12, "unit": "fp",
        "min_stock": 10, "stock": 5,    # LOW
        "barcode": "8001200124004",
        "description": (
            "Färsk buffelmozzarella DOP från Campania. "
            "Mjuk, krämig konsistens med mild mjölksyra. "
            "Levereras i vassle. Bäst-före 7 dagar. Kylkedja."
        ),
        "image_url": _p("mozzarella"),
    },
    {
        "name": "Pistaschkräm Siciliansk 1 kg",
        "sku": "DELI-PISTACHIO-1KG",
        "category": "Importerade Delikatesser",
        "sell": 490, "cost": 265, "tax": 12, "unit": "fp",
        "min_stock": 6, "stock": 24,
        "barcode": "8032472001502",
        "description": (
            "100 % ren pistaschpasta från Bronte, Sicilien. "
            "Intensiv nötig smak utan tillsatser. "
            "Perfekt för gelato, pralin och siciliansk cannoli-fyllning."
        ),
        "image_url": _p("pistachio-paste"),
    },
    {
        "name": "Kaviarlök Röd Lumpfish 50 g",
        "sku": "DELI-CAVIAR-RED-50",
        "category": "Importerade Delikatesser",
        "sell": 195, "cost": 92, "tax": 12, "unit": "fp",
        "min_stock": 10, "stock": 55,
        "barcode": "7312345000099",
        "description": (
            "Röd rom av lumpfish, naturligt saltad. "
            "Används som dekoration på canapéer, smörgåstårta "
            "och skaldjursrätter. 50 g glasburk. Kylvara."
        ),
        "image_url": _p("red-caviar"),
    },

    # ── Nötter & Torkad Frukt ──────────────────────────────────────────────────
    {
        "name": "Pistaschnötter Rostade Saltade 1 kg",
        "sku": "NUT-PISTA-RS-1KG",
        "category": "Nötter & Torkad Frukt",
        "sell": 189, "cost": 89, "tax": 12, "unit": "fp",
        "min_stock": 15, "stock": 112,
        "barcode": "4006000100001",
        "description": (
            "Iranska pistaschnötter, rostade och lätt saltade. "
            "Delade med skal. Ideal som bar-snack, "
            "granola-topping och bakverk. 1 kg ziplock."
        ),
        "image_url": _p("pistachios"),
    },
    {
        "name": "Cashewnötter Rå Ekologisk 1 kg",
        "sku": "NUT-CASHEW-RAW-1KG",
        "category": "Nötter & Torkad Frukt",
        "sell": 169, "cost": 80, "tax": 12, "unit": "fp",
        "min_stock": 15, "stock": 78,
        "barcode": "4006000200002",
        "description": (
            "Helvita råa cashewnötter från Vietnam. KRAV-ekologisk. "
            "W180-storlek, stor och köttig. "
            "Passar rostning, nöt­mjölk och vegansk cashew-ost."
        ),
        "image_url": _p("cashew-nuts"),
    },
    {
        "name": "Mandel Blancherade 1 kg",
        "sku": "NUT-ALMOND-BLANCH-1KG",
        "category": "Nötter & Torkad Frukt",
        "sell": 149, "cost": 70, "tax": 12, "unit": "fp",
        "min_stock": 20, "stock": 134,
        "barcode": "4006000300003",
        "description": (
            "Skalade blancherade mandlar, California Nonpareil-sort. "
            "Utan hud, milda och söta. Används till "
            "mandelmjöl, marcipan och macarons."
        ),
        "image_url": _p("blanched-almonds"),
    },
    {
        "name": "Valnötter Halvor Premium 1 kg",
        "sku": "NUT-WALNUT-HALF-1KG",
        "category": "Nötter & Torkad Frukt",
        "sell": 195, "cost": 93, "tax": 12, "unit": "fp",
        "min_stock": 12, "stock": 67,
        "barcode": "4006000400004",
        "description": (
            "Chilenska valnötshalvor extra light, klass I. "
            "Rik omega-3-profil. Passar dessert, sallad "
            "och nötbröd. 1 kg vakuumförpackning."
        ),
        "image_url": _p("walnut-halves"),
    },
    {
        "name": "Torkade Aprikoser Kalcedon 1 kg",
        "sku": "NUT-APRICOT-DRY-1KG",
        "category": "Nötter & Torkad Frukt",
        "sell": 129, "cost": 60, "tax": 12, "unit": "fp",
        "min_stock": 12, "stock": 89,
        "barcode": "4006000500005",
        "description": (
            "Turkiska torkade aprikoser utan svavel (SO₂-fri). "
            "Naturligt bruna, söta och tuggiga. "
            "Passar energibar, müsli och lagrad fruktkaka."
        ),
        "image_url": _p("dried-apricots"),
    },
    {
        "name": "Dadlar Medjool Färsk 500 g",
        "sku": "NUT-DATE-MEDJ-500",
        "category": "Nötter & Torkad Frukt",
        "sell": 159, "cost": 74, "tax": 12, "unit": "fp",
        "min_stock": 10, "stock": 43,
        "barcode": "7290005003031",
        "description": (
            "Israeliska Medjool-dadlar, storlek Jumbo. "
            "Saftiga, karamelliga med mjuk konsistens. "
            "Perfekt snack, smoothies och raw-dessert. 500 g ask."
        ),
        "image_url": _p("medjool-dates"),
    },
    {
        "name": "Blandnöt Premium Mix 1 kg",
        "sku": "NUT-MIXED-PREM-1KG",
        "category": "Nötter & Torkad Frukt",
        "sell": 229, "cost": 109, "tax": 12, "unit": "fp",
        "min_stock": 15, "stock": 102,
        "barcode": "4006000800008",
        "description": (
            "Premiumlandning: cashew, mandel, macadamia, pekannöt och valnöt. "
            "Lätt rostad, utan salt. Serveras som "
            "bar-snack och hotellfrukosten. 1 kg påse."
        ),
        "image_url": _p("mixed-premium-nuts"),
    },
    {
        "name": "Sultanrosiner Ekologisk 1 kg",
        "sku": "NUT-RAISIN-EKO-1KG",
        "category": "Nötter & Torkad Frukt",
        "sell": 89, "cost": 40, "tax": 12, "unit": "fp",
        "min_stock": 20, "stock": 210,
        "barcode": "4006000700007",
        "description": (
            "Ekologiska sultanarosiner från Turkiet, utan olja. "
            "Söta och saftiga. Passar müsli, fruktkaka, "
            "granola och kexkakor."
        ),
        "image_url": _p("sultana-raisins"),
    },

    # ── Bakutrustning & Tillbehör ──────────────────────────────────────────────
    {
        "name": "Degblandare KitchenAid Artisan 4,8 L Röd",
        "sku": "EQUIP-KA-ARTISAN-48",
        "category": "Bakutrustning & Tillbehör",
        "sell": 6990, "cost": 4200, "tax": 25, "unit": "st",
        "min_stock": 2, "stock": 8,
        "barcode": "5413184109241",
        "description": (
            "KitchenAid Artisan Stand Mixer 4,8 L i Imperial Red. "
            "10 hastigheter, 300 W. Inkl. vispare, degkrok och flatblandare. "
            "Gjutjärnskropp med emaljlack. 5 års garanti."
        ),
        "image_url": _p("kitchenaid-artisan"),
    },
    {
        "name": "Handmixer KitchenAid 5-hastigheter",
        "sku": "EQUIP-KA-HANDMIX",
        "category": "Bakutrustning & Tillbehör",
        "sell": 1690, "cost": 990, "tax": 25, "unit": "st",
        "min_stock": 5, "stock": 17,
        "barcode": "5413184089741",
        "description": (
            "KitchenAid 5KHM9212 handmixer med 9 hastigheter. "
            "Turbo boost-funktion. Inkl. vispar, degkrokar och turbovisp. "
            "Mjuk start-teknik. 220 W. 2 års garanti."
        ),
        "image_url": _p("hand-mixer"),
    },
    {
        "name": "Bakplåt Perforerad Professionell 60×40 cm",
        "sku": "EQUIP-TRAY-PERF-60",
        "category": "Bakutrustning & Tillbehör",
        "sell": 249, "cost": 118, "tax": 25, "unit": "st",
        "min_stock": 10, "stock": 58,
        "barcode": "8033836420001",
        "description": (
            "Gastronorm-kompatibel perforerad bakplåt 60×40 cm i aluminiserat stål. "
            "Luftcirkulationsperforering ger jämn bränd botten. "
            "Diskmaskinssäker. Används i professionella ugnar."
        ),
        "image_url": _p("baking-tray"),
    },
    {
        "name": "Spritspåsar Engångs 53 cm 100-pack",
        "sku": "EQUIP-PIPING-100P",
        "category": "Bakutrustning & Tillbehör",
        "sell": 149, "cost": 68, "tax": 25, "unit": "förp",
        "min_stock": 15, "stock": 88,
        "barcode": "5900242000049",
        "description": (
            "Transparenta PE-spritspåsar 53 cm, 100 per pack. "
            "Tjocklek 60 μm, passar både varma och kalla fyllningar. "
            "Klipps till önskad storlek. Livsmedelsgodkänd plast."
        ),
        "image_url": _p("piping-bags"),
    },
    {
        "name": "Silikonmatta Non-stick 60×40 cm",
        "sku": "EQUIP-SILMAT-60X40",
        "category": "Bakutrustning & Tillbehör",
        "sell": 295, "cost": 139, "tax": 25, "unit": "st",
        "min_stock": 8, "stock": 36,
        "barcode": "3560233101026",
        "description": (
            "Professionell silikonmatta för ugn, 60×40 cm. "
            "Tål –60 °C till +240 °C. Passar gastronormbrickor. "
            "Återanvändbar >3 000 gånger. FDA-godkänd."
        ),
        "image_url": _p("silicone-mat"),
    },
    {
        "name": "Kökstermometer Digital Instant-read",
        "sku": "EQUIP-THERMO-INSTANT",
        "category": "Bakutrustning & Tillbehör",
        "sell": 349, "cost": 162, "tax": 25, "unit": "st",
        "min_stock": 8, "stock": 41,
        "barcode": "0616613861897",
        "description": (
            "Digital termometer med 3 sekunders avläsning och sondtermometer. "
            "Mätområde –50 till +300 °C. IP65 vattentät. "
            "Magnetisk baksida. Inkl. batterier."
        ),
        "image_url": _p("kitchen-thermometer"),
    },
    {
        "name": "Bakpapper Silikonbeläggning 50×70 cm 500-pack",
        "sku": "EQUIP-PAPAPAPER-500",
        "category": "Bakutrustning & Tillbehör",
        "sell": 189, "cost": 90, "tax": 25, "unit": "förp",
        "min_stock": 15, "stock": 74,
        "barcode": "7394001700189",
        "description": (
            "Dubbelsidig silikonbehandlat bakpapper 50×70 cm. "
            "Tål upp till 230 °C. 500 ark per rulle. "
            "FSC-certifierat. Non-stick utan fett."
        ),
        "image_url": _p("baking-paper"),
    },

    # ── Rengöring & Professionell Hygien ──────────────────────────────────────
    {
        "name": "Diskmedel Professionell Koncentrat 5 L",
        "sku": "CLEAN-DISH-5L",
        "category": "Rengöring & Hygien",
        "sell": 189, "cost": 88, "tax": 25, "unit": "kan",
        "min_stock": 15, "stock": 68,
        "barcode": "7391689100023",
        "description": (
            "Professionellt diskmedel, högt koncentrerat 1:20. "
            "Godkänt för livsmedelshantering. "
            "Skonsamt mot händer, biologiskt nedbrytbart. 5 L dunk."
        ),
        "image_url": _p("dish-soap-professional"),
    },
    {
        "name": "Avfettningsmedel Köksyta Spray 1 L",
        "sku": "CLEAN-DEGREASE-1L",
        "category": "Rengöring & Hygien",
        "sell": 149, "cost": 68, "tax": 25, "unit": "fl",
        "min_stock": 15, "stock": 95,
        "barcode": "7391689200010",
        "description": (
            "Professionellt avfettningsmedel för kök och ugnar. "
            "Löser fett och inbränt på 30 sekunder. "
            "HACCP-kompatibelt. 1 L spray-flaska."
        ),
        "image_url": _p("degreaser-spray"),
    },
    {
        "name": "Handtvål Antimikrobiell pH-neutral 5 L",
        "sku": "CLEAN-HANDSOAP-5L",
        "category": "Rengöring & Hygien",
        "sell": 169, "cost": 80, "tax": 25, "unit": "kan",
        "min_stock": 15, "stock": 112,
        "barcode": "7391689300017",
        "description": (
            "Mild pH-neutral handtvål, antimikrobiell. "
            "Godkänd för livsmedelsbranschen. "
            "Passar alla standardtankdispensers. 5 L refill-dunk."
        ),
        "image_url": _p("hand-soap-professional"),
    },
    {
        "name": "Engångshandskar Vinyl Transparent M 100-pack",
        "sku": "CLEAN-GLOVES-VM-100",
        "category": "Rengöring & Hygien",
        "sell": 89, "cost": 38, "tax": 25, "unit": "förp",
        "min_stock": 30, "stock": 245,
        "barcode": "7394002100089",
        "description": (
            "Puderfria vinylhandskar, livsmedelsgodkända. "
            "Storlek M. 100 per förpackning. "
            "Passar kök, café och livsmedelshantering. CE-märkt."
        ),
        "image_url": _p("vinyl-gloves"),
    },
    {
        "name": "Pappershanddukar Z-fold 300-pack",
        "sku": "CLEAN-PAPHAND-Z300",
        "category": "Rengöring & Hygien",
        "sell": 159, "cost": 74, "tax": 25, "unit": "förp",
        "min_stock": 25, "stock": 178,
        "barcode": "7394002200159",
        "description": (
            "2-lags Z-fold pappershanddukar. 300 ark per förpackning. "
            "Passar Tork- och SCA-dispensers. "
            "Hög absorptionsförmåga. TCF-blekt papper."
        ),
        "image_url": _p("paper-hand-towels"),
    },
    {
        "name": "Skyddsförkläde PE-plast 100-pack",
        "sku": "CLEAN-APRON-PE-100",
        "category": "Rengöring & Hygien",
        "sell": 129, "cost": 59, "tax": 25, "unit": "förp",
        "min_stock": 20, "stock": 134,
        "barcode": "7394002300129",
        "description": (
            "Engångsförkläde i polyeten-plast. Universalstorlek. "
            "Passar kök, bageri och café. "
            "100-pack. Livsmedelsgodkänd plast."
        ),
        "image_url": _p("disposable-apron"),
    },

    # ── Glass & Gelatosortiment ────────────────────────────────────────────────
    {
        "name": "Glassbas Neutral Pulver 1 kg",
        "sku": "ICE-BASE-NEU-1KG",
        "category": "Glass & Gelato",
        "sell": 195, "cost": 92, "tax": 12, "unit": "fp",
        "min_stock": 10, "stock": 48,
        "barcode": "8003170200001",
        "description": (
            "Neutral glassbas för hantverksglass. Ger stabil konsistens "
            "utan överfrysning. Blandas med smaksättning. "
            "1 kg ger ~10 L gelato. Laktosfri version tillgänglig."
        ),
        "image_url": _p("gelato-base"),
    },
    {
        "name": "Mangosorbet Puré Alphonso 1 kg",
        "sku": "ICE-SORBET-MANGO-1KG",
        "category": "Glass & Gelato",
        "sell": 149, "cost": 70, "tax": 12, "unit": "fp",
        "min_stock": 8, "stock": 35,
        "barcode": "8003170200018",
        "description": (
            "Alphonso-mangopuré för sorbettillverkning. "
            "Sockerhalt 16 %. Färsk fruktkaraktär utan tillsatser. "
            "1 kg fryst i Cryovac-påse."
        ),
        "image_url": _p("mango-sorbet"),
    },
    {
        "name": "Glassstabilisator Cremodan SE 30 250 g",
        "sku": "ICE-STAB-CRE-250",
        "category": "Glass & Gelato",
        "sell": 245, "cost": 115, "tax": 12, "unit": "fp",
        "min_stock": 6, "stock": 22,
        "barcode": "5701690001303",
        "description": (
            "Danisco Cremodan SE 30 glasstabilisator. "
            "Kombinerar emulgeringsmedel och hydrokolloid. "
            "Dosering: 3–5 g per liter mix. 250 g burk."
        ),
        "image_url": _p("ice-cream-stabilizer"),
    },
    {
        "name": "Glasskoner Wafer Liten 200-pack",
        "sku": "ICE-CONE-WAFER-200",
        "category": "Glass & Gelato",
        "sell": 189, "cost": 90, "tax": 12, "unit": "förp",
        "min_stock": 15, "stock": 82,
        "barcode": "8001300010014",
        "description": (
            "Klassiska wafer-glasskoner, liten storlek Ø4,5 cm. "
            "200 per kartong. Neutralt smak. "
            "Passar single-scoop servering. Glutenfria versioner på begäran."
        ),
        "image_url": _p("ice-cream-cones"),
    },
    {
        "name": "Doppchocolad Mörk Ready-to-Use 2,5 kg",
        "sku": "ICE-DIPCHOC-DRK-2KG",
        "category": "Glass & Gelato",
        "sell": 350, "cost": 168, "tax": 12, "unit": "fp",
        "min_stock": 8, "stock": 3,    # LOW
        "barcode": "5410522900017",
        "description": (
            "Mörk doppchocolad för glasspinnar och softis. "
            "Stelnar på 30 sekunder. Tempereras vid 45 °C. "
            "2,5 kg block. 54 % kakaoinnehåll."
        ),
        "image_url": _p("dipping-chocolate"),
    },
]

# ── Customers ─────────────────────────────────────────────────────────────────

CUSTOMERS = [
    {
        "company_name": "Café Pascal AB",
        "email": "inkop@cafepascal.se",
        "org_number": "556612-3401",
        "contact": "Emma Lindgren",
        "phone": "08-612 34 01",
        "payment_days": 30,
        "city": "Stockholm",
    },
    {
        "company_name": "Hotel Tylösand AB",
        "email": "ekonomi@tylosand.se",
        "org_number": "556234-5678",
        "contact": "Marcus Ahlberg",
        "phone": "035-305 00",
        "payment_days": 45,
        "city": "Halmstad",
    },
    {
        "company_name": "Göteborgs Konditori & Café AB",
        "email": "bestallning@gbgkonditori.se",
        "org_number": "556789-0144",
        "contact": "Sofia Karlsson",
        "phone": "031-712 34 56",
        "payment_days": 30,
        "city": "Göteborg",
    },
    {
        "company_name": "Restaurang Franzén Gruppen AB",
        "email": "logistik@franzen.se",
        "org_number": "556901-2233",
        "contact": "Björn Franzén",
        "phone": "08-20 85 80",
        "payment_days": 30,
        "city": "Stockholm",
    },
    {
        "company_name": "Nordic Bakery Group AB",
        "email": "order@nordicbakery.se",
        "org_number": "559001-5544",
        "contact": "Ingrid Magnusson",
        "phone": "040-456 78 90",
        "payment_days": 30,
        "city": "Malmö",
    },
    {
        "company_name": "Moment Kaffebar AB",
        "email": "inkop@momentkaffe.se",
        "org_number": "556456-1122",
        "contact": "David Ström",
        "phone": "08-556 78 90",
        "payment_days": 30,
        "city": "Stockholm",
    },
    {
        "company_name": "Fika Studios AB",
        "email": "logistik@fikastudios.se",
        "org_number": "559123-4567",
        "contact": "Anna Eriksson",
        "phone": "018-123 45 67",
        "payment_days": 30,
        "city": "Uppsala",
    },
    {
        "company_name": "Clarion Hotel Stockholm AB",
        "email": "purchasing@clarionsthlm.se",
        "org_number": "556321-0099",
        "contact": "Robert Nilsson",
        "phone": "08-462 10 00",
        "payment_days": 45,
        "city": "Stockholm",
    },
    {
        "company_name": "Broms Café & Delikatess AB",
        "email": "bestall@bromscafe.se",
        "org_number": "559045-3312",
        "contact": "Lisa Broms",
        "phone": "08-640 22 11",
        "payment_days": 30,
        "city": "Stockholm",
    },
    {
        "company_name": "Hermans Trädgårdscafé AB",
        "email": "info@hermans.se",
        "org_number": "556678-9900",
        "contact": "Herman Lundqvist",
        "phone": "08-643 94 80",
        "payment_days": 30,
        "city": "Stockholm",
    },
    {
        "company_name": "Norrtelje Kaffe & Te AB",
        "email": "order@norrteljekaffete.se",
        "org_number": "556500-1234",
        "contact": "Katarina Persson",
        "phone": "0176-100 50",
        "payment_days": 30,
        "city": "Norrtälje",
    },
    {
        "company_name": "Vete-Katten Bageri AB",
        "email": "inkop@vetekatten.se",
        "org_number": "556112-3456",
        "contact": "Gunilla Hansson",
        "phone": "08-21 84 34",
        "payment_days": 45,
        "city": "Stockholm",
    },
    # ── Hotel chains & conference ──────────────────────────────────────────────
    {
        "company_name": "Scandic Hotels Sverige AB",
        "email": "purchasing@scandichotels.se",
        "org_number": "556598-8473",
        "contact": "Johan Andersson",
        "phone": "08-517 517 00",
        "payment_days": 45,
        "city": "Stockholm",
    },
    {
        "company_name": "Elite Hotels of Sweden AB",
        "email": "supply@elite.se",
        "org_number": "556323-1009",
        "contact": "Maria Svensson",
        "phone": "08-566 217 00",
        "payment_days": 45,
        "city": "Stockholm",
    },
    {
        "company_name": "Quality Hotel Friends AB",
        "email": "fb@qualityfriends.se",
        "org_number": "556781-0010",
        "contact": "Anders Lindström",
        "phone": "08-444 66 00",
        "payment_days": 30,
        "city": "Solna",
    },
    # ── Coffee chains ──────────────────────────────────────────────────────────
    {
        "company_name": "Wayne's Coffee Sverige AB",
        "email": "logistik@waynescoffee.se",
        "org_number": "556422-8790",
        "contact": "Sara Ekblom",
        "phone": "08-123 45 00",
        "payment_days": 30,
        "city": "Stockholm",
    },
    {
        "company_name": "Fazer Café Sverige AB",
        "email": "order@fazercafe.se",
        "org_number": "556890-1234",
        "contact": "Mikael Mäkinen",
        "phone": "08-244 98 00",
        "payment_days": 30,
        "city": "Stockholm",
    },
    # ── Bakeries & delis ──────────────────────────────────────────────────────
    {
        "company_name": "Bagarstugans Hantverk AB",
        "email": "inkop@bagarstugan.se",
        "org_number": "556334-7788",
        "contact": "Kristina Bager",
        "phone": "040-198 88 00",
        "payment_days": 30,
        "city": "Malmö",
    },
    {
        "company_name": "Gateau Pastelería AB",
        "email": "supply@gateau.se",
        "org_number": "559201-4433",
        "contact": "Felipe Cruz",
        "phone": "031-711 22 55",
        "payment_days": 30,
        "city": "Göteborg",
    },
    # ── Grocery & retail ──────────────────────────────────────────────────────
    {
        "company_name": "ICA Nära Hornsgatan AB",
        "email": "bestall@icanara-horns.se",
        "org_number": "556567-9901",
        "contact": "Björn Ek",
        "phone": "08-668 12 34",
        "payment_days": 30,
        "city": "Stockholm",
    },
    {
        "company_name": "Axfood Snabbgross AB",
        "email": "grossist@axfood.se",
        "org_number": "556542-7790",
        "contact": "Petra Åkerlund",
        "phone": "08-553 994 00",
        "payment_days": 60,
        "city": "Stockholm",
    },
    # ── Restaurant groups ──────────────────────────────────────────────────────
    {
        "company_name": "Restaurang Jonas & Co AB",
        "email": "kök@jonasrestaurang.se",
        "org_number": "559312-0099",
        "contact": "Jonas Bergkvist",
        "phone": "08-412 34 56",
        "payment_days": 30,
        "city": "Stockholm",
    },
    {
        "company_name": "Teatern Food & Bar AB",
        "email": "mat@teaternkrogen.se",
        "org_number": "556892-3344",
        "contact": "Lisa Dahl",
        "phone": "031-811 22 33",
        "payment_days": 30,
        "city": "Göteborg",
    },
    {
        "company_name": "Stockholms Stadshus Restaurang AB",
        "email": "kansli@stadshusrestaurang.se",
        "org_number": "212000-0142",
        "contact": "Cecilia Bergman",
        "phone": "08-508 29 358",
        "payment_days": 60,
        "city": "Stockholm",
    },
]

# ── Suppliers ─────────────────────────────────────────────────────────────────

SUPPLIERS = [
    {
        "name": "Nordic Coffee Imports AB",
        "email": "order@nordiccoffee.se",
        "phone": "08-456 78 90",
        "lead_days": 5,
        "category": "Kaffe & Te",
    },
    {
        "name": "SCA Food Distribution AB",
        "email": "supply@scafood.se",
        "phone": "031-234 56 78",
        "lead_days": 3,
        "category": "Bakverk & Råvaror",
    },
    {
        "name": "Packaging Solutions Sweden AB",
        "email": "sales@packagingsw.se",
        "phone": "040-345 67 89",
        "lead_days": 4,
        "category": "Förpackning & Engångs",
    },
    {
        "name": "European Tea Masters AB",
        "email": "tea@etmasters.se",
        "phone": "08-789 01 23",
        "lead_days": 7,
        "category": "Kaffe & Te",
    },
    {
        "name": "Maskindepån Sverige AB",
        "email": "order@maskindepan.se",
        "phone": "08-567 89 01",
        "lead_days": 10,
        "category": "Maskiner & Utrustning",
    },
    {
        "name": "Valrhona Nordic Distribution AB",
        "email": "order@valrhona-nordic.se",
        "phone": "08-901 23 45",
        "lead_days": 6,
        "category": "Choklad & Konfektyr",
    },
    {
        "name": "Delikatessimport Stockholm AB",
        "email": "inkop@deliimport.se",
        "phone": "08-234 56 78",
        "lead_days": 8,
        "category": "Importerade Delikatesser",
    },
    {
        "name": "KitchenPro Sverige AB",
        "email": "b2b@kitchenpro.se",
        "phone": "031-456 78 90",
        "lead_days": 5,
        "category": "Bakutrustning & Tillbehör",
    },
]

TODAY = date.today()


def _months_ago(n: int) -> date:
    d = TODAY.replace(day=1)
    for _ in range(n):
        d = (d - timedelta(days=1)).replace(day=1)
    return d


def _rand_day_in_month(base: date) -> date:
    import calendar
    _, last = calendar.monthrange(base.year, base.month)
    return base.replace(day=rng.randint(1, last))


# ── Main seeder ───────────────────────────────────────────────────────────────

async def main() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    user_id = await _create_supabase_user()

    async with Session() as db:
        org_id        = await _create_org(db, user_id)
        wh_id         = await _create_warehouse(db, org_id)
        supplier_ids  = await _create_suppliers(db, org_id)
        product_ids   = await _create_products(db, org_id, wh_id, supplier_ids)
        customer_ids  = await _create_customers(db, org_id)
        await _create_invoices(db, org_id, customer_ids, product_ids)
        await _create_stock_movements(db, org_id, wh_id, product_ids)
        await _create_pos_sessions(db, org_id, product_ids, user_id)
        await _create_purchase_orders(db, org_id, supplier_ids, product_ids)
        await db.commit()

    await engine.dispose()

    cats = sorted({p["category"] for p in PRODUCTS})
    print()
    print("=" * 60)
    print("  Varuflow storgrossen demo — klar!")
    print("=" * 60)
    print(f"  Företag  : {DEMO_ORG_NAME}")
    print(f"  Email    : {DEMO_EMAIL}")
    print(f"  Lösenord : {DEMO_PASSWORD}")
    print()
    print("  Inläst data:")
    print(f"    {len(PRODUCTS)} produkter med bilder i {len(cats)} kategorier")
    for c in cats:
        n = sum(1 for p in PRODUCTS if p["category"] == c)
        print(f"      · {c} ({n} produkter)")
    print(f"    {len(CUSTOMERS)} kunder (hotell, kafé, restaurang, dagligvaror)")
    print(f"    {len(SUPPLIERS)} leverantörer")
    print(f"    ~97 fakturor med grossistvolymer (6 månaders historik)")
    print(f"    90 dagars lagerrörelser")
    print(f"    5 kassasessioner med transaktioner")
    print(f"    3 inköpsorder (DRAFT / SENT / RECEIVED)")
    print("=" * 60)


# ── Step helpers ──────────────────────────────────────────────────────────────

async def _create_supabase_user() -> uuid.UUID:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        fake = uuid.uuid4()
        print(f"[WARN] Supabase ej konfigurerat — använder fake user_id {fake}")
        return fake

    async with httpx.AsyncClient() as c:
        r = await c.post(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            },
            json={
                "email": DEMO_EMAIL,
                "password": DEMO_PASSWORD,
                "email_confirm": True,
                "user_metadata": {"full_name": "Demo Admin"},
            },
            timeout=30,
        )

    if r.status_code == 422:
        async with httpx.AsyncClient() as c:
            r2 = await c.get(
                f"{SUPABASE_URL}/auth/v1/admin/users",
                headers={
                    "apikey": SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                },
                params={"email": DEMO_EMAIL},
                timeout=30,
            )
        users = r2.json().get("users", [])
        if users:
            uid = uuid.UUID(users[0]["id"])
            print(f"[INFO] Supabase-användare finns redan: {uid}")
            return uid

    if r.status_code not in (200, 201):
        fake = uuid.uuid4()
        print(f"[WARN] Supabase returned {r.status_code} — fake id {fake}")
        return fake

    uid = uuid.UUID(r.json()["id"])
    print(f"[OK] Supabase-användare skapad: {uid}")
    return uid


async def _create_org(db: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    from app.features.auth.organization import Organization, OrganizationMember, OrgPlan, OrgRole

    org = Organization(
        id=uuid.uuid4(),
        name=DEMO_ORG_NAME,
        org_number=DEMO_ORG_NO,
        vat_number=DEMO_VAT,
        address=DEMO_ADDRESS,
        plan=OrgPlan.PRO,
        base_currency="SEK",
        fiscal_year_start=1,
        onboarding_wizard_completed=True,
        country_code="SE",
    )
    db.add(org)
    await db.flush()

    member = OrganizationMember(
        org_id=org.id,
        user_id=user_id,
        role=OrgRole.OWNER,
    )
    db.add(member)
    await db.flush()
    print(f"[OK] Organisation: {org.name} ({org.id})")
    return org.id


async def _create_warehouse(db: AsyncSession, org_id: uuid.UUID) -> uuid.UUID:
    from app.features.inventory.models import Warehouse

    wh = Warehouse(
        org_id=org_id,
        name="Centrallager Stockholm",
        location="Rosenlundsgatan 44, 118 53 Stockholm",
    )
    db.add(wh)
    await db.flush()
    print(f"[OK] Lager: {wh.name}")
    return wh.id


async def _create_suppliers(db: AsyncSession, org_id: uuid.UUID) -> list[uuid.UUID]:
    from app.features.inventory.models import Supplier

    ids = []
    for s in SUPPLIERS:
        sup = Supplier(
            org_id=org_id,
            name=s["name"],
            email=s["email"],
            phone=s.get("phone"),
            default_lead_days=s.get("lead_days"),
        )
        db.add(sup)
        await db.flush()
        ids.append(sup.id)
    print(f"[OK] {len(SUPPLIERS)} leverantörer")
    return ids


async def _create_products(
    db: AsyncSession,
    org_id: uuid.UUID,
    wh_id: uuid.UUID,
    supplier_ids: list[uuid.UUID],
) -> list[uuid.UUID]:
    from app.features.inventory.models import Product, StockLevel, StockMovement, StockMovementType

    # Map category → supplier index (8 suppliers now)
    cat_sup = {
        "Kaffe & Te":                 supplier_ids[0],
        "Maskiner & Utrustning":      supplier_ids[4],
        "Bakverk & Råvaror":          supplier_ids[1],
        "Förpackning & Engångs":      supplier_ids[2],
        "Dryck & Syroper":            supplier_ids[0],
        "Choklad & Konfektyr":        supplier_ids[5],
        "Importerade Delikatesser":   supplier_ids[6],
        "Nötter & Torkad Frukt":      supplier_ids[1],
        "Bakutrustning & Tillbehör":  supplier_ids[7],
        "Rengöring & Hygien":         supplier_ids[2],
        "Glass & Gelato":             supplier_ids[1],
    }

    ids = []
    for p in PRODUCTS:
        prod = Product(
            org_id=org_id,
            name=p["name"],
            sku=p["sku"],
            category=p["category"],
            sell_price=Decimal(str(p["sell"])),
            purchase_price=Decimal(str(p["cost"])),
            tax_rate=Decimal(str(p["tax"])),
            unit=p["unit"],
            reorder_level=p["min_stock"],
            image_url=p.get("image_url"),
            description=p.get("description"),
            barcode=p.get("barcode"),
            preferred_supplier_id=cat_sup.get(p["category"]),
            auto_reorder_enabled=True,
            is_active=True,
        )
        db.add(prod)
        await db.flush()
        ids.append(prod.id)

        # Opening stock level
        sl = StockLevel(
            org_id=org_id,
            product_id=prod.id,
            warehouse_id=wh_id,
            quantity=Decimal(str(p["stock"])),
        )
        db.add(sl)

        # Initial IN movement
        opening_date = datetime.combine(
            TODAY - timedelta(days=180), datetime.min.time()
        ).replace(tzinfo=timezone.utc)
        mv = StockMovement(
            org_id=org_id,
            product_id=prod.id,
            warehouse_id=wh_id,
            type=StockMovementType.IN,
            quantity=int(p["stock"]),
            reference="Ingående lager",
            created_at=opening_date,
        )
        db.add(mv)

    await db.flush()
    print(f"[OK] {len(PRODUCTS)} produkter med bilder och lagernivåer")
    return ids


async def _create_customers(db: AsyncSession, org_id: uuid.UUID) -> list[uuid.UUID]:
    from app.features.invoicing.models import Customer

    ids = []
    for c in CUSTOMERS:
        cust = Customer(
            org_id=org_id,
            company_name=c["company_name"],
            email=c["email"],
            org_number=c["org_number"],
            phone=c.get("phone"),
            payment_terms_days=c.get("payment_days", 30),
        )
        db.add(cust)
        await db.flush()
        ids.append(cust.id)
    print(f"[OK] {len(CUSTOMERS)} kunder")
    return ids


async def _create_invoices(
    db: AsyncSession,
    org_id: uuid.UUID,
    customer_ids: list[uuid.UUID],
    product_ids: list[uuid.UUID],
) -> None:
    from app.features.invoicing.models import Invoice, InvoiceLineItem, InvoiceStatus, Payment, PaymentMethod
    from app.features.invoicing.model_quotes import Quote as _Quote  # noqa: F401 — registers quotes table
    from app.features.bookings.models import Staff as _Staff  # noqa: F401 — registers staff table

    def _pick_lines(n: int | None = None) -> list[dict]:
        n = n or rng.randint(2, 5)
        idxs = rng.sample(range(len(PRODUCTS)), k=min(n, len(PRODUCTS)))
        # Wholesale quantities: 10–150 units per line
        return [{"idx": i, "qty": rng.randint(10, 150)} for i in idxs]

    inv_n = 1

    for month_offset, count, mix in [
        (5, 12, {"PAID": 1.0}),
        (4, 15, {"PAID": 1.0}),
        (3, 18, {"PAID": 0.9,  "OVERDUE": 0.1}),
        (2, 20, {"PAID": 0.85, "OVERDUE": 0.15}),
        (1, 18, {"PAID": 0.6,  "SENT": 0.25, "OVERDUE": 0.15}),
        (0, 14, {"SENT": 0.5,  "DRAFT": 0.25, "PAID": 0.25}),
    ]:
        base = _months_ago(month_offset)
        for _ in range(count):
            issue = _rand_day_in_month(base)
            r_val = rng.random()
            cum = 0.0
            status_str = "PAID"
            for s, prob in mix.items():
                cum += prob
                if r_val <= cum:
                    status_str = s
                    break
            if issue > TODAY:
                status_str = "DRAFT"

            status = InvoiceStatus[status_str]
            payment_days = CUSTOMERS[rng.randint(0, len(CUSTOMERS) - 1)]["payment_days"]
            due = issue + timedelta(days=payment_days)
            if status == InvoiceStatus.OVERDUE and due > TODAY:
                due = TODAY - timedelta(days=rng.randint(5, 25))

            cust_id = customer_ids[rng.randint(0, len(customer_ids) - 1)]
            lines = _pick_lines()

            subtotal  = Decimal("0")
            vat_total = Decimal("0")
            for line in lines:
                p = PRODUCTS[line["idx"]]
                ex = Decimal(str(p["sell"])) * line["qty"]
                vat = ex * Decimal(str(p["tax"])) / 100
                subtotal  += ex
                vat_total += vat

            total = subtotal + vat_total
            inv_num = f"FAK-{inv_n:04d}"
            inv_n += 1

            inv = Invoice(
                org_id=org_id,
                customer_id=cust_id,
                invoice_number=inv_num,
                issue_date=issue,
                due_date=due,
                status=status,
                currency="SEK",
                subtotal=subtotal,
                vat_amount=vat_total,
                total_sek=total,
            )
            db.add(inv)
            await db.flush()

            for line in lines:
                p = PRODUCTS[line["idx"]]
                ex  = Decimal(str(p["sell"])) * line["qty"]
                vat = ex * Decimal(str(p["tax"])) / 100
                li = InvoiceLineItem(
                    invoice_id=inv.id,
                    description=p["name"],
                    quantity=Decimal(str(line["qty"])),
                    unit_price=Decimal(str(p["sell"])),
                    tax_rate=Decimal(str(p["tax"])),
                    line_total=ex + vat,
                )
                db.add(li)

            if status == InvoiceStatus.PAID:
                paid_date = issue + timedelta(days=rng.randint(3, payment_days))
                db.add(Payment(
                    org_id=org_id,
                    invoice_id=inv.id,
                    amount=total,
                    payment_date=paid_date,
                    method=PaymentMethod.BANK_TRANSFER,
                    reference="Inbetalning via banköverföring",
                ))

    await db.flush()
    print(f"[OK] {inv_n - 1} fakturor (6 månaders historik)")


async def _create_stock_movements(
    db: AsyncSession,
    org_id: uuid.UUID,
    wh_id: uuid.UUID,
    product_ids: list[uuid.UUID],
) -> None:
    from app.features.inventory.models import StockMovement, StockMovementType

    count = 0
    for days_ago in range(90, 0, -1):
        mv_date = datetime.combine(
            TODAY - timedelta(days=days_ago), datetime.min.time()
        ).replace(tzinfo=timezone.utc)
        for _ in range(rng.randint(2, 5)):
            idx = rng.randint(0, len(product_ids) - 1)
            qty = rng.randint(1, 12)
            db.add(StockMovement(
                org_id=org_id,
                product_id=product_ids[idx],
                warehouse_id=wh_id,
                type=StockMovementType.OUT,
                quantity=qty,
                reference=f"Försäljning {(TODAY - timedelta(days=days_ago)).isoformat()}",
                created_at=mv_date,
            ))
            count += 1

    await db.flush()
    print(f"[OK] {count} lagerrörelser (90 dagar)")


async def _create_pos_sessions(
    db: AsyncSession,
    org_id: uuid.UUID,
    product_ids: list[uuid.UUID],
    user_id: uuid.UUID,
) -> None:
    from app.features.pos.models import (
        PosSession, PosSessionStatus, PosSale, PosSaleItem, PosPaymentMethod,
    )

    pm_choices = [PosPaymentMethod.CARD, PosPaymentMethod.SWISH, PosPaymentMethod.CASH]
    sale_n = 1

    for days_ago, n_tx in [(21, 18), (14, 22), (7, 26), (3, 19), (1, 14)]:
        sess_date = TODAY - timedelta(days=days_ago)
        session = PosSession(
            org_id=org_id,
            cashier_user_id=user_id,
            status=PosSessionStatus.CLOSED,
            opened_at=datetime.combine(sess_date, datetime.min.time()).replace(
                tzinfo=timezone.utc, hour=8
            ),
            closed_at=datetime.combine(sess_date, datetime.min.time()).replace(
                tzinfo=timezone.utc, hour=17
            ),
            opening_float=Decimal("2000"),
            counted_cash=Decimal(str(2000 + rng.randint(5000, 18000))),
        )
        db.add(session)
        await db.flush()

        for _ in range(n_tx):
            idx = rng.randint(0, len(product_ids) - 1)
            p = PRODUCTS[idx]
            qty = Decimal(str(rng.randint(1, 4)))
            unit = Decimal(str(p["sell"]))
            tax  = Decimal(str(p["tax"]))
            line_ex  = unit * qty
            line_vat = (line_ex * tax / 100).quantize(Decimal("0.01"))
            total    = line_ex + line_vat
            pm = rng.choice(pm_choices)

            sale = PosSale(
                org_id=org_id,
                session_id=session.id,
                sale_number=f"POS-{sale_n:06d}",
                subtotal=line_ex,
                vat_amount=line_vat,
                total=total,
                payment_method=pm,
                created_at=datetime.combine(sess_date, datetime.min.time()).replace(
                    tzinfo=timezone.utc, hour=rng.randint(9, 16)
                ),
            )
            sale_n += 1
            db.add(sale)
            await db.flush()

            db.add(PosSaleItem(
                sale_id=sale.id,
                product_id=product_ids[idx],
                description=p["name"],
                quantity=qty,
                unit_price=unit,
                tax_rate=tax,
                line_total=total,
            ))

    await db.flush()
    print(f"[OK] 3 kassasessioner ({sale_n - 1} transaktioner)")


async def _create_purchase_orders(
    db: AsyncSession,
    org_id: uuid.UUID,
    supplier_ids: list[uuid.UUID],
    product_ids: list[uuid.UUID],
) -> None:
    try:
        from app.features.inventory.models import PurchaseOrder, PurchaseOrderItem
    except ImportError:
        print("[SKIP] Inköpsordermodeller ej tillgängliga — hoppar över")
        return

    from app.features.inventory.models import PurchaseOrderStatus

    specs = [
        {"status": PurchaseOrderStatus.DRAFT,    "sup": 0, "prods": [0, 1, 2, 5]},
        {"status": PurchaseOrderStatus.SENT,     "sup": 4, "prods": [10, 11, 12]},
        {"status": PurchaseOrderStatus.RECEIVED, "sup": 2, "prods": [24, 27, 28, 30]},
    ]

    for spec in specs:
        po_total = Decimal("0")
        po = PurchaseOrder(
            org_id=org_id,
            supplier_id=supplier_ids[spec["sup"]],
            status=spec["status"],
            total=po_total,
        )
        db.add(po)
        await db.flush()

        for pidx in spec["prods"]:
            if pidx >= len(PRODUCTS) or pidx >= len(product_ids):
                continue
            p = PRODUCTS[pidx]
            qty = rng.randint(15, 50)
            unit = Decimal(str(p["cost"]))
            line = unit * qty
            po_total += line
            db.add(PurchaseOrderItem(
                purchase_order_id=po.id,
                product_id=product_ids[pidx],
                quantity=qty,
                unit_price=unit,
                line_total=line,
            ))

        po.total = po_total

    await db.flush()
    print("[OK] 3 inköpsorder (DRAFT / SENT / RECEIVED)")


if __name__ == "__main__":
    asyncio.run(main())
