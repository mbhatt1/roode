## Example 2: Configuration

You can customize app behavior by providing a configuration object.

### Code  

```js
const config = {
  logLevel: 'info',
  port: 3000
}

const app = createApp(config);
app.run();

// Expected output:
// [INFO] App is running on port 3000
```

The `createApp` function accepts an optional config object. Here we:

1. Define a config object to set log level and port 
2. Pass the config to `createApp`
3. The app will run with those customized settings