---
layout: page 
title: Troubleshooting Guide
permalink: /guides/troubleshooting/
---  

# Troubleshooting Guide

This guide covers common issues and errors you may encounter when working with Foo, along with steps to resolve them.

## CLI Errors

**Error: EACCES: permission denied**

This error occurs when running CLI commands like `foo new` without adequate file permissions. 

To fix it:

1. Check if Foo was installed globally by following the [installation guide](/guides/installation).
2. Reinstall globally by running (with sudo if required):
   ```
   npm install -g foo
   ```

## Runtime Errors

..

## Need More Help?

If you encounter other issues not covered here, check the resources below for more support:

- Search open and closed [GitHub issues](https://github.com/foo/foo/issues) for similar problems
- Ask on the [Foo Community Forums](https://community.fooweb.io)
- Email [foo-support@company.com](mailto:foo-support@company.com) for paid support