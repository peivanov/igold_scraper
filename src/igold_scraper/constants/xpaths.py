"""XPath selectors for igold.bg website structure."""

# Category page selectors
CATEGORY_PRODUCT_LINKS = '//dd[@class="kv__member-name"]/a[1][@href and @href!="#"]/@href'
CATEGORY_PRODUCT_ELEMENTS = '//dd[@class="kv__member-name"]/a[1][@href and @href!="#"]'
CATEGORY_PRODUCT_TITLE = "string(.//h2)"

# Category page - Product list items (for price extraction)
CATEGORY_PRODUCT_ITEMS = (
    '//li[@class="kv__member-item" and '
    'not(contains(@class, "product-list-title"))]'
)
# Within each product item:
CATEGORY_ITEM_URL = 'string(.//dd[@class="kv__member-name"]/a[1]/@href)'
CATEGORY_ITEM_NAME = 'string(.//dd[@class="kv__member-name"]//h2)'
CATEGORY_ITEM_BUY_PRICE_EUR = (
    'normalize-space(.//dt[contains(@class, "kv__member-cat-left")]//'
    'span[contains(@class, "catE-") or contains(@class, "cat2E-")])'
)
CATEGORY_ITEM_SELL_PRICE_EUR = (
    'normalize-space(.//dt[contains(@class, "kv__member-cat-right")]//'
    'span[contains(@class, "catE-")])'
)

# Product page - Basic info
PRODUCT_TITLE = "string(//main//h1)"

# Product page - Price table (regular-product table)
PRICE_SELL_EUR = "string(//regular-product//table/tbody/tr[1]/td[2]/span)"
PRICE_BUY_EUR = "string(//regular-product//table/tbody/tr[4]/td[2]/span)"

# Product page - Details container
PRODUCT_DETAILS_CONTAINER = (
    '//div[contains(@class, "memberheader__meta") and contains(@class, "effect")]'
)
PRODUCT_DETAILS_PARAGRAPHS = ".//p"
