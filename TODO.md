# TODO

## In Progress

### UPC Cache (local)
- [ ] Add `upc_cache` table to database (upc, product_type, brand, product_line, caliber, weight_gr,
      bullet_type, bc_g1, bc_g7, rounds_per_box, primer_type, primer_model, powder_name, image_path, updated_at)
- [ ] Update barcode lookup endpoint: check `upc_cache` first, fall back to UPC Item DB API
- [ ] Pull product image from UPC Item DB API response (`images` array) and save locally on first lookup
- [ ] Add `upc` hidden field to all add-item forms (populated when a barcode is scanned)
- [ ] On form submit, upsert final form values into `upc_cache` keyed by UPC
- [ ] Let user override cached image with their own photo

## Future

### Unlimited Photos per Item
- [ ] Create `ItemPhoto` table (id, item_type, item_id, image_path, sort_order, created_at)
- [ ] Add generic photo management endpoints (add, delete, reorder, set primary)
- [ ] Migrate existing `image_path` / `image_path_2` columns to new table
- [ ] Update all serializers to return photos array
- [ ] Update all detail page galleries to handle N photos
- [ ] Remove hardcoded 2-photo limit from upload logic

### Public Community UPC API
- [ ] Expose `upc_cache` as a public read API endpoint
- [ ] Add a write/correction endpoint for community contributions
- [ ] Seed database by scraping manufacturer catalogs (Hornady, Federal, Winchester, Remington, etc.)
- [ ] Add rate limiting, auth, and hosting if opened to public
- [ ] Consider crowdsourced voting/moderation for data quality
