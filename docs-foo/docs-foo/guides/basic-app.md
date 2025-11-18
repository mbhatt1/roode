---
layout: page
title: Building a Basic Foo App
permalink: /guides/basic-app/
---

# Building a Basic Foo App

This guide covers how to build a simple application using the Foo framework. By the end, you'll have a working todo list app to manage your tasks.  

## Prerequisites

- Foo is installed
- You have a code editor set up

## Steps

1. **Create a new Foo app**

   ```bash
   foo new todo-app
   ```

   This will generate a new app directory with a starter repo.

2. **Install dependencies**

   ```bash 
   cd todo-app
   npm install
   ```

3. **Define the TodoItem model**

   Create a new file `models/TodoItem.js`:

   ```js
   // models/TodoItem.js
   import { Model } from 'foo'; 

   export class TodoItem extends Model {
     static entity = 'todos'

     static fields() {
       return {
         text: this.attr(),
         completed: this.attr('boolean')
       }
     }
   }
   ```

   This defines a `TodoItem` model with `text` and `completed` fields.

4. **Create the TodoList component**

   ...
