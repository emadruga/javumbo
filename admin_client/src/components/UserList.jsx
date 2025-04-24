import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const ITEMS_PER_PAGE = 5;

function UserList() {
  const [users, setUsers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [currentPage, setCurrentPage] = useState(1); // State for current page
  const [activeDropdownUserId, setActiveDropdownUserId] = useState(null); // State for active dropdown
  const navigate = useNavigate();

  useEffect(() => {
    const fetchUsers = async () => {
      setIsLoading(true);
      setError(null);
      // API endpoint for fetching regular users
      const apiUrl = 'http://localhost:9000/admin/users'; 

      try {
        const response = await fetch(apiUrl);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        setUsers(data);
      } catch (fetchError) {
        console.error("Error fetching users:", fetchError);
        setError(fetchError.message || 'Could not fetch users. Please check the server.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchUsers();

    // Cleanup function (optional, not strictly needed for this fetch)
    return () => {
      // You could potentially abort the fetch request here if the component unmounts
    };
  }, []); // Empty dependency array means this effect runs once on mount

  // --- Pagination Logic --- 
  const totalPages = Math.ceil(users.length / ITEMS_PER_PAGE);
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
  const endIndex = startIndex + ITEMS_PER_PAGE;
  const paginatedUsers = users.slice(startIndex, endIndex);

  const handlePreviousPage = () => {
    setCurrentPage(prev => Math.max(prev - 1, 1)); // Don't go below page 1
    setActiveDropdownUserId(null); // Close dropdown on page change
  };

  const handleNextPage = () => {
    setCurrentPage(prev => Math.min(prev + 1, totalPages)); // Don't go above total pages
    setActiveDropdownUserId(null); // Close dropdown on page change
  };

  // --- Dropdown Toggle Logic --- 
  const toggleDropdown = (userId) => {
    setActiveDropdownUserId(prevId => (prevId === userId ? null : userId));
  };

  // --- Action Handlers --- 
  const handleViewDecks = (username) => {
    setActiveDropdownUserId(null);
    navigate(`/users/${username}/decks`);
  };

  const handleUserInfo = (user) => {
    alert(`User Info:\nUsername: ${user.username}\nName: ${user.name || 'N/A'}\n(Last Review: Not implemented)`);
    setActiveDropdownUserId(null); // Close dropdown after action
  };

  if (isLoading) {
    return <div>Loading users...</div>;
  }

  if (error) {
    return <div style={{ color: 'red' }}>Error: {error}</div>;
  }

  return (
    <div style={{ maxWidth: '600px', margin: 'auto' }}>
      <h2>User List</h2>
      {users.length === 0 ? (
        <p>No users found.</p>
      ) : (
        <>
          <div>
            {paginatedUsers.map(user => (
              <div 
                key={user.user_id}
                style={{
                  border: '1px solid #ccc',
                  borderRadius: '8px',
                  padding: '15px',
                  marginBottom: '10px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  position: 'relative' // Needed for absolute positioning of dropdown
                }}
              >
                <span style={{ fontWeight: 'bold' }}>
                  {user.name || 'N/A'} ({user.username})
                </span>

                {/* --- Gear Button and Dropdown --- */}
                <div> {/* Container for button and dropdown */} 
                  <button
                    onClick={() => toggleDropdown(user.user_id)} // Toggle this user's dropdown
                    style={{ 
                      background: 'none', 
                      border: 'none', 
                      fontSize: '1.2em', 
                      cursor: 'pointer' 
                    }}
                  >
                    ⚙️
                  </button>

                  {/* Conditionally render Dropdown */} 
                  {activeDropdownUserId === user.user_id && (
                    <div style={{
                      position: 'absolute',
                      right: '0',
                      top: '40px', // Position below the gear button
                      backgroundColor: 'white',
                      border: '1px solid #ccc',
                      borderRadius: '4px',
                      boxShadow: '0 2px 5px rgba(0,0,0,0.15)',
                      zIndex: 10, // Ensure dropdown is above other elements
                      minWidth: '150px'
                    }}>
                      <ul style={{ listStyle: 'none', margin: 0, padding: '5px 0' }}>
                        <li style={{ padding: '8px 12px', cursor: 'pointer', color: 'black' }}
                            onClick={() => handleViewDecks(user.username)}>
                           View Decks
                        </li>
                        <li style={{ padding: '8px 12px', cursor: 'pointer', color: 'black' }}
                            onClick={() => handleUserInfo(user)}>
                           List User Info
                        </li>
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {totalPages > 1 && (
            <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
              <button onClick={handlePreviousPage} disabled={currentPage === 1}>
                Previous
              </button>
              <span style={{ margin: '0 15px' }}>
                Page {currentPage} of {totalPages}
              </span>
              <button onClick={handleNextPage} disabled={currentPage === totalPages}>
                Next
              </button>
            </div>
          )}
        </>
      )}
      {/* TODO: Add actual Dropdown menu for gear button */}
    </div>
  );
}

export default UserList; 