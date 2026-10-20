# Consistent Unicode search and indexed name pagination

- [x] Reproduce Cyrillic/Latin case search and mixed-case name pagination on
  disposable PostgreSQL 17 initialized with locale C.
- [x] Share Unicode SQL normalization across products, people and communities.
  Keep literal search escaping, bounded scalar queries and public visibility.
  Use the same expression for ordering, cursor comparison and indexes.
- [x] Add reversible index migration and reject cursors from the former ordering.
  Verify schema agreement, upgrade/downgrade data preservation, PostgreSQL plans,
  public contracts and focused tests. No production migration in this stage.
- [x] Update the local project map and release evidence with measured scope.
