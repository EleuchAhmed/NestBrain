"""Scan Zotero SQLite for collections and items (copies DB first to avoid lock)."""
import sqlite3, os, shutil, tempfile

src = os.path.join(os.path.expanduser("~"), "Zotero", "zotero.sqlite")
dst = os.path.join(tempfile.gettempdir(), "zotero_scan_copy.sqlite")
shutil.copy2(src, dst)

conn = sqlite3.connect(dst)
cur = conn.cursor()

# Collections
cur.execute("SELECT collectionID, collectionName, key FROM collections")
colls = cur.fetchall()
print("=== Collections ===")
for c in colls:
    print(f"  {c[0]}: {c[1]} (key={c[2]})")

print()

# Items with collection membership
cur.execute("""
    SELECT i.key, it.typeName, idv.value as title, ci.collectionID
    FROM items i
    JOIN itemTypes it ON it.itemTypeID = i.itemTypeID
    LEFT JOIN itemData id ON id.itemID = i.itemID
    LEFT JOIN fields f ON f.fieldID = id.fieldID AND f.fieldName = 'title'
    LEFT JOIN itemDataValues idv ON idv.valueID = id.valueID
    LEFT JOIN collectionItems ci ON ci.itemID = i.itemID
    WHERE i.itemID NOT IN (SELECT itemID FROM deletedItems)
      AND it.typeName NOT IN ('attachment', 'note')
    ORDER BY i.dateAdded DESC
    LIMIT 20
""")
items = cur.fetchall()
print("=== Recent Items ===")
for it in items:
    print(f"  {it[0]} | {it[1]} | {it[2]} | collID={it[3]}")

print()

# PDF attachments
cur.execute("""
    SELECT ia.parentItemID, ia.path, i.key as attachmentKey, i2.key as parentKey
    FROM itemAttachments ia
    JOIN items i ON i.itemID = ia.itemID
    LEFT JOIN items i2 ON i2.itemID = ia.parentItemID
    WHERE ia.contentType = 'application/pdf'
    ORDER BY i.dateAdded DESC
    LIMIT 10
""")
pdfs = cur.fetchall()
print("=== PDF Attachments ===")
for p in pdfs:
    print(f"  parentKey={p[3]} | attachKey={p[2]} | path={p[1]}")

# Check URLs
print()
cur.execute("""
    SELECT i.key, idv.value
    FROM items i
    JOIN itemData id ON id.itemID = i.itemID
    JOIN fields f ON f.fieldID = id.fieldID AND f.fieldName = 'url'
    JOIN itemDataValues idv ON idv.valueID = id.valueID
    WHERE i.itemID NOT IN (SELECT itemID FROM deletedItems)
    ORDER BY i.dateAdded DESC
    LIMIT 10
""")
urls = cur.fetchall()
print("=== URLs ===")
for u in urls:
    print(f"  {u[0]} | {u[1]}")

conn.close()
os.remove(dst)
