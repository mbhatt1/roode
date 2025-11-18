## Maintaining the Foo Documentation Site

### Building Locally

1. Install Ruby and Bundler if not already installed
2. Run `bundle install` to install dependencies
3. Run `bundle exec jekyll serve` to build and serve the site at http://localhost:4000

### Adding New Pages

1. Create a new Markdown file in the appropriate directory (_api, _guides, _tutorials)
2. Add front matter following Jekyll conventions
3. Add the new file path to the relevant collection in _config.yml

### Deploying Updates

1. Run `bundle exec jekyll build` to generate the _site directory
2. Copy the contents of _site to the production hosting location
