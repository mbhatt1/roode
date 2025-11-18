/**
 * Sample TypeScript file for testing tree-sitter parsing.
 */

interface User {
    name: string;
    age: number;
}

type Status = 'active' | 'inactive';

class UserManager {
    private users: User[] = [];
    
    constructor() {
        this.users = [];
    }
    
    addUser(user: User): void {
        this.users.push(user);
    }
    
    getUser(name: string): User | undefined {
        return this.users.find(u => u.name === name);
    }
}

function processUser(user: User): string {
    return `${user.name} (${user.age})`;
}

const arrowFunction = (a: number, b: number): number => {
    return a + b;
};

export { UserManager, processUser };