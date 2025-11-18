---
title: Code Snippets
---

# Common Code Snippets

This page contains frequently used code snippets for common patterns and utilities when working with Foo.

## Helper Functions

### `isValuePresent`

```js
/**
 * Checks if a value is present in array or object values
 * @param {Array|Object} collection
 * @param {*} value
 */
function isValuePresent(collection, value) {
  if (Array.isArray(collection)) {
    return collection.includes(value);
  } else {
    return Object.values(collection).includes(value);
  }
}
```

Example usage:

```js
const numbers = [1, 2, 3];
console.log(isValuePresent(numbers, 2)); // true

const obj = { a: 1, b: 2, c: 3};
console.log(isValuePresent(obj, 1)); // true
```

... [Add more snippets]