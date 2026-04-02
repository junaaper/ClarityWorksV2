const { Pool } = require('pg');
require('dotenv').config();

const pool = new Pool({
  connectionString: process.env.DATABASE_URL || 'postgresql://clarityworks_user:clarityworks_pass@localhost:5432/clarityworks_db',
});

async function getUsers() {
  try {
    const result = await pool.query(`
      SELECT id, email, full_name, role, is_active, created_at
      FROM users
      ORDER BY created_at DESC
    `);

    console.log('\n=== ALL USERS ===\n');
    result.rows.forEach(user => {
      console.log(`ID: ${user.id}`);
      console.log(`Email: ${user.email}`);
      console.log(`Name: ${user.full_name}`);
      console.log(`Role: ${user.role}`);
      console.log(`Active: ${user.is_active}`);
      console.log(`Created: ${user.created_at}`);
      console.log('---');
    });

    const admins = result.rows.filter(u => u.role === 'admin');
    const users = result.rows.filter(u => u.role === 'user');

    console.log('\n=== ADMIN USERS ===');
    admins.forEach(u => console.log(`- ${u.email} (${u.full_name})`));

    console.log('\n=== REGULAR USERS ===');
    users.forEach(u => console.log(`- ${u.email} (${u.full_name})`));

    console.log(`\nTotal: ${result.rows.length} users (${admins.length} admins, ${users.length} regular users)`);

  } catch (error) {
    console.error('Error querying database:', error.message);
  } finally {
    await pool.end();
  }
}

getUsers();
