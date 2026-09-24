import { ComponentGroup } from '@/data/sidebar-components';
import { useEffect, useMemo, useState } from 'react';

export function useComponentGroups(componentGroups: ComponentGroup[]) {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeItem, setActiveItem] = useState<string | null>(null);
  const [openGroups, setOpenGroups] = useState<string[]>([]); // Start with all groups collapsed

  const isSearching = searchQuery.length > 0;

  // Filter groups and items based on search query
  const filteredGroups = useMemo(() => {
    if (!searchQuery) return componentGroups;

    return componentGroups.map(group => {
      // Filter items within the group
      const filteredItems = group.items.filter(item => 
        item.name.toLowerCase().includes(searchQuery.toLowerCase())
      );

      // Return group with filtered items
      return {
        ...group,
        items: filteredItems
      };
    }).filter(group => group.items.length > 0); // Only include groups with matching items
  }, [componentGroups, searchQuery]);

  // Handle item selection
  const handleItemClick = (itemName: string) => {
    setActiveItem(itemName);
    // Additional logic for handling component selection could go here
  };

  // Expand every group that still has a match while a search is active.
  useEffect(() => {
    if (!searchQuery) return;
    setOpenGroups(filteredGroups.map(group => group.name));
  }, [searchQuery, filteredGroups]);

  // Handle accordion value changes
  const handleAccordionChange = (value: string[]) => {
    // Only update if we're not actively searching
    if (!searchQuery) {
      setOpenGroups(value);
    } else {
      // During search, we need to preserve expanded groups that have matches
      const matchingGroups = filteredGroups.map(group => group.name);
      // Keep all matching groups open while allowing manual toggling of others
      const newValue = value.filter(group => matchingGroups.includes(group));
      if (newValue.length < matchingGroups.length) {
        // If user is closing a search result group, allow that
        setOpenGroups(newValue);
      } else {
        // User is opening a new group during search
        setOpenGroups(value);
      }
    }
  };

  return {
    searchQuery,
    setSearchQuery,
    activeItem,
    setActiveItem,
    openGroups,
    setOpenGroups,
    isSearching,
    filteredGroups,
    handleItemClick,
    handleAccordionChange
  };
} 