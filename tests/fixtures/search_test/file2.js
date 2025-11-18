// JavaScript test file for search testing

function searchData(data) {
  // TODO: Implement search
  const results = [];
  for (const item of data) {
    if (item.match(/search/)) {
      results.push(item);
    }
  }
  return results;
}

class DataSearcher {
  constructor() {
    this.data = [];
  }
  
  search(query) {
    // TODO: Add fuzzy matching
    return this.data.filter(item => item.includes(query));
  }
}

export { searchData, DataSearcher };